"""Opt-in WhatsApp pilot: text-only capture, conservative templates, internal notices.

No public routes; no passenger sending endpoint. No fabricated consent on group capture.
"""
import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, Response
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
import httpx
from crm.db import connection
from crm.service import audit


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')


def classify(text):
    t=normalize(text)
    demand=bool(re.search(r'\b(busco|buscamos|necesito|necesitamos|quisiera|queremos|precio|cuanto|recomiendan|consulta|looking for|need|procuro|preciso)\b|有没有|需要',t))
    offer=bool(re.search(r'\b(ofrezco|ofrecemos|reservas al|tarifas promocionales|tenemos disponibilidad)\b',t))
    service='otro'
    if re.search(r'\b(transfer|aeropuerto|airport)\b',t): service='transfer'
    elif re.search(r'\b(traslado|transporte|transferir)\b',t): service='traslado'
    elif re.search(r'\b(alojamiento|cabana|casa|hospedaje|hotel|accommodation|lodging)\b',t):
        service='alojamiento_yala' if 'yala' in t else 'alojamiento_carmen' if ('carmen' in t or 'cienaga' in t) else 'otro'
    elif re.search(r'\b(alquil|alquiler)\w*.*\b(auto|vehiculo|mobi)\b',t): service='alquiler_vehiculo'
    elif re.search(r'\b(excursion|excursiones|trekking|travesia|salinas|hornocal|tour|hiking)\b',t): service='actividad'
    if offer and not demand:return 'oferta',service,''
    if not demand:return 'revisar',service,''
    questions={
        'transfer':'¿Qué fecha y horario necesitan, desde qué aeropuerto y hacia qué destino? ¿Cuántas personas viajan y con cuánto equipaje?',
        'traslado':'¿Desde dónde y hacia dónde necesitan viajar, en qué fecha y cuántas personas son?',
        'alojamiento_yala':'¿Qué fechas de ingreso y salida necesitan y cuántos adultos y menores se alojarían en Yala?',
        'alojamiento_carmen':'¿Qué fechas de ingreso y salida necesitan y cuántas personas se alojarían en El Carmen?',
        'alquiler_vehiculo':'¿Para qué fechas necesitan el vehículo y dónde desean retirarlo y devolverlo?',
        'actividad':'¿Qué actividad les interesa, para qué fecha y cuántas personas participarían?',
        'otro':'¿Qué servicio necesitan, para qué fechas y cuántas personas serían?'}
    return 'posible_consulta',service,'¡Hola! Somos Agencia ROMA. '+questions[service]+' Con esos datos podemos consultar opciones. Disponibilidad y tarifa sujetas a confirmación.'


class Event(BaseModel):
    event_id:str=Field(pattern=r'^[a-f0-9]{64}$')
    account_id:UUID
    group_id:str=Field(pattern=r'^[0-9-]+@g\.us$',max_length=100)
    group_name:str=Field(max_length=200)
    sender_id:str=Field(max_length=150)
    message_id:str=Field(min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=5000)
    timestamp:float=Field(ge=0,le=4102444800)

    @field_validator('text')
    @classmethod
    def nonempty(cls,v):
        if not v.strip():raise ValueError('Mensaje vacío')
        return v


async def receive(body):
    async with connection() as conn:
        row=await (await conn.execute('''INSERT INTO whatsapp_events(event_id,account_id,group_id,group_name,sender_id,message_id,text,source_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING RETURNING event_id''',
          (body.event_id,body.account_id,body.group_id,body.group_name,body.sender_id,body.message_id,body.text,datetime.fromtimestamp(body.timestamp,timezone.utc)))).fetchone()
    return {'accepted':True,'created':bool(row)}


async def process_batch():
    processed=0
    async with connection() as conn:
        rows=await (await conn.execute('''SELECT * FROM whatsapp_events WHERE processed_at IS NULL
          ORDER BY received_at FOR UPDATE SKIP LOCKED LIMIT 20''')).fetchall()
        for row in rows:
            classification,category,draft=classify(row['text'])
            enquiry_id=None;notice='';delivery='not_required'
            if classification=='posible_consulta':
                request_id=uuid5(NAMESPACE_URL,'roma:whatsapp:'+row['event_id'])
                summary=('OPORTUNIDAD DETECTADA EN GRUPO (revisar antes de contactar)\nGrupo: '+row['group_name']+
                         '\nFecha: '+row['source_at'].isoformat()+'\n\nConsulta original:\n'+row['text'])[:6000]
                result=await (await conn.execute('''INSERT INTO enquiries(request_id,channel,summary,next_action)
                  VALUES(%s,'whatsapp',%s,%s) RETURNING id,code''',(request_id,summary,'Revisar borrador en WhatsApp / Capturas; responder manualmente.'))).fetchone()
                enquiry_id=result['id']
                await conn.execute('INSERT INTO enquiry_categories VALUES(%s,%s)',(enquiry_id,category))
                await audit(conn,'whatsapp-pilot','capture','enquiry',enquiry_id,{'source':'selected_group','event_id':row['event_id']})
                notice=('ROMA · Oportunidad '+result['code']+'\nOrigen: '+row['group_name']+'\n\nConsulta:\n'+row['text'][:1200]+
                        '\n\nBORRADOR PARA REVISAR (no enviado al pasajero):\n'+draft+
                        '\n\nAbrir panel VPN → WhatsApp / Capturas. Validar contexto, datos ya informados y destinatario antes de responder.')
                delivery='pending'
            await conn.execute('''UPDATE whatsapp_events SET processed_at=now(),classification=%s,enquiry_id=%s,draft=%s,notice=%s,delivery_status=%s WHERE event_id=%s''',
                               (classification,enquiry_id,draft,notice,delivery,row['event_id']))
            processed+=1
    return processed


async def bridge(method,path,body=None):
    token=os.getenv('WA_BRIDGE_TOKEN','')
    if len(token)<32:raise HTTPException(503,'Instalar módulo WhatsApp con la guía de despliegue')
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r=await client.request(method,'http://wa-bridge:3000'+path,headers={'Authorization':'Bearer '+token},json=body)
        if r.is_error:
            raise HTTPException(502,'El conector rechazó la operación: '+str(r.json().get('detail','Revisar conexión'))[:200])
        return r.json()
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'Conector no disponible; la consulta permanece guardada')


async def dispatch_batch():
    results=[]
    # Only one dispatcher; limits each run to five notices. Connection timeout is bounded.
    async with connection() as conn:
        locked=await (await conn.execute('SELECT pg_try_advisory_xact_lock(19413003) AS locked')).fetchone()
        if not locked['locked']:return []
        rows=await (await conn.execute('''SELECT event_id,notice FROM whatsapp_events WHERE delivery_status='pending' AND enquiry_id IS NOT NULL
          AND (last_attempt_at IS NULL OR last_attempt_at<now()-interval '1 minute') ORDER BY received_at LIMIT 5''')).fetchall()
        for row in rows:
            await conn.execute('UPDATE whatsapp_events SET last_attempt_at=now() WHERE event_id=%s',(row['event_id'],))
            try: result=await bridge('POST','/send-alert',{'event_id':row['event_id'],'text':row['notice']})
            except HTTPException:results.append('pending');continue
            state=result.get('status','unknown')
            if state=='sending':state='unknown'
            if state not in ('pending','sent','unknown','paused'):state='unknown'
            await conn.execute('UPDATE whatsapp_events SET delivery_status=%s WHERE event_id=%s',(state,row['event_id']))
            results.append(state)
    return results


class AccountInput(BaseModel):
    label:str=Field(min_length=1,max_length=80)

class ConfigInput(BaseModel):
    sources:list[str]=Field(max_length=100)
    internal_group:str=Field(max_length=100)


def install(app,operator,automation):
    auth=HTTPBearer(auto_error=False)
    def connector(credentials:HTTPAuthorizationCredentials|None=Depends(auth)):
        token=os.getenv('WA_BRIDGE_TOKEN','')
        if len(token)<32:raise HTTPException(503,'Conector no configurado')
        if not credentials or not secrets.compare_digest(credentials.credentials.encode(),token.encode()):raise HTTPException(401,'No autorizado')

    @app.get('/whatsapp',response_class=HTMLResponse,dependencies=[Depends(operator)])
    async def page():return Path(__file__).with_name('whatsapp.html').read_text()
    @app.get('/whatsapp.js',dependencies=[Depends(operator)])
    async def script():return Response(Path(__file__).with_name('whatsapp.js').read_text(),media_type='text/javascript')
    @app.get('/api/whatsapp/accounts',dependencies=[Depends(operator)])
    async def accounts():return await bridge('GET','/accounts')
    @app.post('/api/whatsapp/accounts',dependencies=[Depends(operator)])
    async def create(b:AccountInput):return await bridge('POST','/accounts',b.model_dump())
    @app.get('/api/whatsapp/accounts/{account_id}/{action}',dependencies=[Depends(operator)])
    async def get_account(account_id:UUID,action:str):
        if action not in ('qr','groups','config'):raise HTTPException(404)
        return await bridge('GET',f'/accounts/{account_id}/{action}')
    @app.post('/api/whatsapp/accounts/{account_id}/config',dependencies=[Depends(operator)])
    async def configure(account_id:UUID,b:ConfigInput):return await bridge('POST',f'/accounts/{account_id}/config',b.model_dump())
    @app.post('/api/whatsapp/accounts/{account_id}/{action}',dependencies=[Depends(operator)])
    async def action(account_id:UUID,action:str):
        if action not in ('start','pause','logout'):raise HTTPException(404)
        return await bridge('POST',f'/accounts/{account_id}/{action}',{})
    @app.get('/api/whatsapp/events',dependencies=[Depends(operator)])
    async def events():
        async with connection() as conn:
            return await (await conn.execute('''SELECT w.event_id,w.group_name,w.text,w.source_at,w.classification,w.draft,w.delivery_status,e.code
               FROM whatsapp_events w LEFT JOIN enquiries e ON e.id=w.enquiry_id ORDER BY w.received_at DESC LIMIT 100''')).fetchall()
    @app.post('/api/whatsapp/process',dependencies=[Depends(operator)])
    async def process():return {'processed':await process_batch()}
    @app.post('/api/whatsapp/dispatch',dependencies=[Depends(operator)])
    async def dispatch():return {'results':await dispatch_batch()}
    @app.post('/integrations/whatsapp/events',dependencies=[Depends(connector)])
    async def inbound(b:Event):return await receive(b)
    @app.post('/automation/whatsapp/run',dependencies=[Depends(automation)])
    async def run():return {'processed':await process_batch(),'results':await dispatch_batch()}
