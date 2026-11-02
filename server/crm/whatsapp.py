"""Opt-in WhatsApp pilot: text-only capture, conservative templates, internal notices.

No public routes; no passenger sending endpoint. No fabricated consent on group capture.
"""
import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, Response
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
import httpx
from crm.db import connection
from crm.service import audit
from crm.whatsapp_filter import classify_message
from crm.passenger_requests import install_admin, dispatch_responses
from crm.whatsapp_ficha import Ficha, extract, missing, draft_for
from psycopg.types.json import Jsonb
from urllib.parse import urlencode
from typing import Literal


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')


def classify(text):
    classification,service=classify_message(text)
    if classification!='posible_consulta':return classification,service,''
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
    sender_name:str=Field(default='',max_length=120)
    sender_phone:str=Field(default='',pattern=r'^(?:\+[1-9][0-9]{7,14})?$')
    phone_source:Literal['','participant','participant_alt','lid_mapping']=''
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
        row=await (await conn.execute('''INSERT INTO whatsapp_events(event_id,account_id,group_id,group_name,sender_id,message_id,text,source_at,sender_name,sender_phone,phone_source)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING RETURNING event_id''',
          (body.event_id,body.account_id,body.group_id,body.group_name,body.sender_id,body.message_id,body.text,datetime.fromtimestamp(body.timestamp,timezone.utc),body.sender_name,body.sender_phone,body.phone_source))).fetchone()
    return {'accepted':True,'created':bool(row)}


async def process_batch():
    processed=0
    async with connection() as conn:
        rows=await (await conn.execute('''SELECT * FROM whatsapp_events WHERE processed_at IS NULL
          ORDER BY received_at FOR UPDATE SKIP LOCKED LIMIT 20''')).fetchall()
        for row in rows:
            classification,category,draft=classify(row['text'])
            if row.get('manual_category'):classification,category='posible_consulta',row['manual_category']
            ficha=extract(row['text'],row['source_at'],category,row['sender_name'],row['sender_phone'])
            if classification=='posible_consulta':draft=draft_for(ficha)
            enquiry_id=None;notice='';delivery='not_required'
            if classification=='posible_consulta':
                request_id=uuid5(NAMESPACE_URL,'roma:whatsapp:'+row['event_id'])
                summary=('OPORTUNIDAD DETECTADA EN GRUPO (revisar antes de contactar)\nGrupo: '+row['group_name']+
                         '\nFecha: '+row['source_at'].isoformat()+'\n\nConsulta original:\n'+row['text'])[:6000]
                result=await (await conn.execute('''INSERT INTO enquiries(request_id,channel,summary,next_action,name,contact,passengers)
                  VALUES(%s,'whatsapp',%s,%s,%s,%s,%s) RETURNING id,code''',(request_id,summary,'Revisar ficha y datos faltantes en WhatsApp / Capturas.',ficha.name,ficha.phone,ficha.passengers))).fetchone()
                enquiry_id=result['id']
                await conn.execute('INSERT INTO enquiry_categories VALUES(%s,%s)',(enquiry_id,category))
                await audit(conn,'whatsapp-pilot','capture','enquiry',enquiry_id,{'source':'selected_group','event_id':row['event_id']})
                notice=('ROMA · Oportunidad '+result['code']+'\nOrigen: '+row['group_name']+'\nAutor: '+(row['sender_name'] or 'Sin nombre')+'\nContacto: '+(row['sender_phone'] or 'Número no disponible')+'\n\nConsulta:\n'+row['text'][:1200]+
                        '\n\nBORRADOR PARA REVISAR (no enviado al pasajero):\n'+draft+
                        '\n\nAbrir panel VPN → WhatsApp / Capturas. Validar contexto, datos ya informados y destinatario antes de responder.')
                delivery='pending'
            await conn.execute('''UPDATE whatsapp_events SET processed_at=now(),classification=%s,enquiry_id=%s,draft=%s,notice=%s,delivery_status=%s,ficha=%s,ficha_updated_at=now(),ficha_version=ficha_version+1 WHERE event_id=%s''',
                               (classification,enquiry_id,draft,notice,delivery,Jsonb(ficha.model_dump(mode='json')),row['event_id']))
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
    # Only one dispatcher; limits each run to three initial notices. Connection timeout is bounded.
    async with connection() as conn:
        locked=await (await conn.execute('SELECT pg_try_advisory_xact_lock(19413003) AS locked')).fetchone()
        if not locked['locked']:return []
        rows=await (await conn.execute('''SELECT event_id,notice FROM whatsapp_events WHERE delivery_status='pending' AND enquiry_id IS NOT NULL
          AND (last_attempt_at IS NULL OR last_attempt_at<now()-interval '1 minute') ORDER BY received_at LIMIT 3''')).fetchall()
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


class FichaSave(BaseModel):
    version:int=Field(ge=1)
    enquiry_version:int=Field(ge=1)
    ficha:Ficha
    draft:str=Field(min_length=1,max_length=6000)

    @field_validator('draft')
    @classmethod
    def draft_not_empty(cls,v):
        if not v.strip():raise ValueError('Completar el borrador')
        return v


def ficha_result(ficha,draft):
    url=''
    if ficha.contact_confirmed and ficha.phone and draft.strip():
        url='https://wa.me/'+ficha.phone[1:]+'?'+urlencode({'text':draft})
    return {'ficha':ficha.model_dump(mode='json'),'missing':missing(ficha),'draft':draft,'whatsapp_url':url}


async def save_ficha(event_id,body,actor):
    async with connection() as conn:
        row=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s FOR UPDATE',(event_id,))).fetchone()
        if not row:raise HTTPException(404,'Captura inexistente')
        if not row['enquiry_id']:raise HTTPException(409,'Primero clasificar la consulta')
        if row['ficha_version']!=body.version:raise HTTPException(409,'La ficha cambió. Actualizá las capturas antes de guardar.')
        enquiry=await (await conn.execute('SELECT version FROM enquiries WHERE id=%s FOR UPDATE',(row['enquiry_id'],))).fetchone()
        if enquiry['version']!=body.enquiry_version:raise HTTPException(409,'La consulta cambió en Gestión comercial. Actualizá antes de guardar.')
        f=body.ficha
        await conn.execute('UPDATE whatsapp_events SET ficha=%s,draft=%s,ficha_version=ficha_version+1,ficha_updated_at=now() WHERE event_id=%s',
            (Jsonb(f.model_dump(mode='json')),body.draft,event_id))
        await conn.execute('''UPDATE enquiries SET name=%s,contact=%s,passengers=%s,travel_start=%s,travel_end=%s,
            updated_at=now(),version=version+1 WHERE id=%s''',
            (f.name,f.phone,f.passengers,f.travel_date if f.date_confirmed else None,f.end_date if f.date_confirmed else None,row['enquiry_id']))
        old_category=(row['ficha'] or {}).get('category')
        if old_category and old_category!=f.category:
            await conn.execute('DELETE FROM enquiry_categories WHERE enquiry_id=%s AND category_code=%s',(row['enquiry_id'],old_category))
        await conn.execute('INSERT INTO enquiry_categories VALUES(%s,%s) ON CONFLICT DO NOTHING',(row['enquiry_id'],f.category))
        await audit(conn,actor,'save_whatsapp_ficha','enquiry',row['enquiry_id'],{'event_id':event_id,'version':body.version+1})
    # Preserve the immutable internal notice and delivery ledger. Saving never sends a message.
    return {**ficha_result(f,body.draft),'ficha_version':body.version+1,'enquiry_version':body.enquiry_version+1}


class AccountInput(BaseModel):
    label:str=Field(min_length=1,max_length=80)

class ConfigInput(BaseModel):
    sources:list[str]=Field(max_length=100)
    internal_group:str=Field(max_length=100)


def install(app,operator,automation):
    install_admin(app,operator)
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
    async def events(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),filter:str='consultas',code:str=Query('',max_length=40)):
        clauses={'consultas':'w.enquiry_id IS NOT NULL','pendientes':'w.processed_at IS NULL','revisar':"w.classification='revisar'",'oferta':"w.classification='oferta'",'irrelevante':"w.classification='irrelevante'",'todos':'TRUE','datos_recibidos':"pr.status='received'"}
        if filter not in clauses:raise HTTPException(400,'Filtro inválido')
        async with connection() as conn:
            return await (await conn.execute("""SELECT w.event_id,w.group_name,w.text,w.source_at,w.classification,w.draft,w.delivery_status,
                w.sender_name,w.sender_phone,w.phone_source,w.ficha,w.ficha_version,e.code,e.version AS enquiry_version,
                pr.id AS request_id,pr.status AS request_status,pr.expires_at AS request_expires_at,
                pr.response AS passenger_response,pr.snapshot AS request_snapshot
                FROM whatsapp_events w LEFT JOIN enquiries e ON e.id=w.enquiry_id
                LEFT JOIN LATERAL (SELECT * FROM passenger_requests WHERE event_id=w.event_id ORDER BY created_at DESC LIMIT 1) pr ON TRUE
                WHERE """+clauses[filter]+" AND (%s='' OR e.code=%s) ORDER BY w.received_at DESC,w.event_id DESC LIMIT %s OFFSET %s",(code.upper(),code.upper(),limit,offset))).fetchall()
    @app.post('/api/whatsapp/events/{event_id}/promote',dependencies=[Depends(operator)])
    async def promote(event_id:str):
        async with connection() as conn:
            row=await (await conn.execute('SELECT enquiry_id FROM whatsapp_events WHERE event_id=%s FOR UPDATE',(event_id,))).fetchone()
            if not row:raise HTTPException(404,'Captura inexistente')
            if row['enquiry_id']:return {'queued':False}
            await conn.execute("UPDATE whatsapp_events SET manual_category='otro',processed_at=NULL WHERE event_id=%s",(event_id,))
        await process_batch()
        return {'queued':True}
    @app.post('/api/whatsapp/preview',dependencies=[Depends(operator)])
    async def preview(b:Ficha):return ficha_result(b,draft_for(b))
    @app.post('/api/whatsapp/events/{event_id}/extract',dependencies=[Depends(operator)])
    async def extract_original(event_id:str):
        async with connection() as conn:
            row=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s',(event_id,))).fetchone()
        if not row:raise HTTPException(404,'Captura inexistente')
        _,category,_=classify(row['text'])
        f=extract(row['text'],row['source_at'],category,row['sender_name'],row['sender_phone'])
        return ficha_result(f,draft_for(f))
    @app.put('/api/whatsapp/events/{event_id}/ficha')
    async def save(event_id:str,b:FichaSave,actor=Depends(operator)):
        return await save_ficha(event_id,b,actor)
    @app.post('/api/whatsapp/process',dependencies=[Depends(operator)])
    async def process():return {'processed':await process_batch()}
    @app.post('/api/whatsapp/dispatch',dependencies=[Depends(operator)])
    async def dispatch():return {'results':await dispatch_batch(),'form_results':await dispatch_responses(bridge)}
    @app.post('/integrations/whatsapp/events',dependencies=[Depends(connector)])
    async def inbound(b:Event):return await receive(b)
    @app.post('/automation/whatsapp/run',dependencies=[Depends(automation)])
    async def run():return {'processed':await process_batch(),'results':await dispatch_batch(),'form_results':await dispatch_responses(bridge)}
