"""Scoped, expiring passenger forms; raw tokens never stored in the database or URL path."""
import hashlib
import os
import secrets
import time
from collections import deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb
from crm.db import connection, enabled
from crm.service import audit
from crm.whatsapp_ficha import Ficha, draft_for

router=APIRouter()
PUBLIC_FIELDS=('name','phone','passengers','origin','destination','travel_date','end_date','time','flight','luggage','activity')
STATES={'awaiting':'Faltan datos','received':'Datos recibidos · revisar','reviewed':'Datos revisados para cotizar','revoked':'Enlace anulado'}


def base_url():
    value=os.getenv('CRM_PUBLIC_BASE_URL','https://asistente.romanomad.travel').rstrip('/')
    u=urlsplit(value)
    if u.scheme!='https' or not u.netloc or u.username or u.password or u.path or u.query or u.fragment:
        raise HTTPException(503,'Configurar CRM_PUBLIC_BASE_URL como origen HTTPS')
    return value


def digest(token):return hashlib.sha256(token.encode()).hexdigest()


class Version(BaseModel):
    version:int=Field(ge=1)
    enquiry_version:int=Field(ge=1)

class Token(BaseModel):
    token:str=Field(pattern=r'^[A-Za-z0-9_-]{43}$')

class PassengerDetails(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=120)
    phone:str=Field(default='',pattern=r'^(?:\+[1-9][0-9]{7,14})?$')
    passengers:int=Field(ge=1,le=500)
    origin:str=Field(default='',max_length=200)
    destination:str=Field(default='',max_length=200)
    travel_date:date|None=None
    end_date:date|None=None
    time:str=Field(default='',max_length=5)
    flight:str=Field(default='',max_length=80)
    luggage:str=Field(default='',max_length=200)
    activity:str=Field(default='',max_length=200)
    answer:str=Field(default='',max_length=2000)
    comments:str=Field(default='',max_length=2000)
    consent:Literal[True]

    @model_validator(mode='after')
    def valid(self):
        if not self.name.strip():raise ValueError('Completá tu nombre')
        Ficha(**{k:getattr(self,k) for k in PUBLIC_FIELDS})
        return self

class Submission(Token):
    submission_id:UUID
    details:PassengerDetails


def safe_snapshot(f):
    d=f.model_dump(mode='json')
    return {**{k:d[k] for k in PUBLIC_FIELDS},'category':d['category'],'extra_question':d['extra_question']}


async def issue(event_id,body,actor):
    origin=base_url()
    async with connection() as conn:
        row=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s FOR UPDATE',(event_id,))).fetchone()
        if not row or not row['enquiry_id']:raise HTTPException(404,'Primero clasificar esta consulta')
        enquiry=await (await conn.execute('SELECT * FROM enquiries WHERE id=%s FOR UPDATE',(row['enquiry_id'],))).fetchone()
        if row['ficha_version']!=body.version or enquiry['version']!=body.enquiry_version:
            raise HTTPException(409,'La ficha cambió. Actualizá antes de crear el enlace.')
        if not row['ficha']:raise HTTPException(409,'Prepará y guardá la ficha antes de crear el enlace.')
        previous=await (await conn.execute("SELECT * FROM passenger_requests WHERE event_id=%s AND status IN ('awaiting','received') FOR UPDATE",(event_id,))).fetchone()
        if previous and previous['status']=='received':raise HTTPException(409,'Hay una respuesta recibida. Revisala antes de solicitar nuevos datos.')
        if previous:await conn.execute("UPDATE passenger_requests SET status='revoked' WHERE id=%s",(previous['id'],))
        token=secrets.token_urlsafe(32);request_id=uuid4();expires=datetime.now(timezone.utc)+timedelta(days=7)
        f=Ficha(**row['ficha'])
        await conn.execute('INSERT INTO passenger_requests(id,event_id,enquiry_id,token_hash,snapshot,expires_at) VALUES(%s,%s,%s,%s,%s,%s)',
            (request_id,event_id,row['enquiry_id'],digest(token),Jsonb(safe_snapshot(f)),expires))
        await audit(conn,actor,'request_passenger_details','enquiry',row['enquiry_id'],{'request_id':str(request_id)})
    url=origin+'/solicitud#'+token
    message='¡Hola! Somos Agencia ROMA. Para preparar tu presupuesto, revisá los datos de tu viaje y completá lo que falta en este formulario privado: '+url+'\nEl enlace vence en 7 días. Completarlo no confirma una reserva.'
    return {'id':str(request_id),'url':url,'message':message,'expires_at':expires,'status':'awaiting'}


async def read_form(token):
    async with connection() as conn:
        row=await (await conn.execute('SELECT snapshot,status,expires_at FROM passenger_requests WHERE token_hash=%s',(digest(token),))).fetchone()
    if not row or row['status']=='revoked' or row['expires_at']<=datetime.now(timezone.utc):raise HTTPException(410,'El enlace venció o ya no está disponible. Pedile uno nuevo a ROMA.')
    if row['status']!='awaiting':return {'submitted':True}
    return {'submitted':False,'fields':row['snapshot'],'expires_at':row['expires_at']}


async def submit_form(body):
    async with connection() as conn:
        # Same lock order as issuing/reviewing: event, request, enquiry.
        ref=await (await conn.execute('SELECT event_id FROM passenger_requests WHERE token_hash=%s',(digest(body.token),))).fetchone()
        if not ref:raise HTTPException(410,'Enlace no disponible')
        await conn.execute('SELECT event_id FROM whatsapp_events WHERE event_id=%s FOR UPDATE',(ref['event_id'],))
        row=await (await conn.execute('SELECT * FROM passenger_requests WHERE token_hash=%s FOR UPDATE',(digest(body.token),))).fetchone()
        if not row or row['status']=='revoked' or row['expires_at']<=datetime.now(timezone.utc):raise HTTPException(410,'El enlace venció o ya no está disponible')
        if row['status']!='awaiting':
            if row['submission_id']==body.submission_id and row['response']==body.details.model_dump(mode='json'):return {'ok':True,'already_received':True}
            raise HTTPException(409,'Este formulario ya fue enviado. Contactá a ROMA para corregirlo.')
        enquiry=await (await conn.execute('SELECT code FROM enquiries WHERE id=%s',(row['enquiry_id'],))).fetchone()
        notice='ROMA · Datos recibidos · '+enquiry['code']+'\nEl pasajero completó el formulario. Abrir panel privado → WhatsApp → Datos recibidos para revisar y aplicar su respuesta antes de cotizar.'
        await conn.execute("UPDATE passenger_requests SET response=%s,status='received',submission_id=%s,submitted_at=now(),notice_status='pending',notice=%s WHERE id=%s",
            (Jsonb(body.details.model_dump(mode='json')),body.submission_id,notice,row['id']))
        await audit(conn,'passenger-form','submit_details','enquiry',row['enquiry_id'],{'request_id':str(row['id']),'consent':'quote-follow-up-v1'})
    return {'ok':True,'already_received':False}


async def apply_response(event_id,request_id,body,actor):
    async with connection() as conn:
        row=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s FOR UPDATE',(event_id,))).fetchone()
        if not row:raise HTTPException(404,'Consulta inexistente')
        req=await (await conn.execute('SELECT * FROM passenger_requests WHERE id=%s AND event_id=%s FOR UPDATE',(request_id,event_id))).fetchone()
        if not req or req['status']!='received':raise HTTPException(409,'No hay una respuesta pendiente de revisión')
        enquiry=await (await conn.execute('SELECT * FROM enquiries WHERE id=%s FOR UPDATE',(row['enquiry_id'],))).fetchone()
        if row['ficha_version']!=body.version or enquiry['version']!=body.enquiry_version:raise HTTPException(409,'La consulta cambió. Actualizá antes de aplicar la respuesta.')
        current=Ficha(**row['ficha']).model_dump(mode='json')
        current.update({k:req['response'][k] for k in PUBLIC_FIELDS})
        current['date_confirmed']=bool(current['travel_date'])
        # The operator must verify the destination number independently before using wa.me.
        current['contact_confirmed']=False
        if req['response'].get('answer'):current['extra_question']=''
        f=Ficha(**current)
        await conn.execute('UPDATE whatsapp_events SET ficha=%s,draft=%s,ficha_version=ficha_version+1,ficha_updated_at=now() WHERE event_id=%s',
            (Jsonb(f.model_dump(mode='json')),draft_for(f),event_id))
        await conn.execute('UPDATE enquiries SET name=%s,contact=%s,passengers=%s,travel_start=%s,travel_end=%s,version=version+1,updated_at=now() WHERE id=%s',
            (f.name,f.phone,f.passengers,f.travel_date,f.end_date,row['enquiry_id']))
        await conn.execute("UPDATE passenger_requests SET status='reviewed',reviewed_at=now() WHERE id=%s",(request_id,))
        await audit(conn,actor,'apply_passenger_details','enquiry',row['enquiry_id'],{'request_id':str(request_id)})
    return {'ok':True}


async def dispatch_responses(bridge):
    results=[]
    async with connection() as conn:
        lock=await (await conn.execute('SELECT pg_try_advisory_xact_lock(19413004) AS locked')).fetchone()
        if not lock['locked']:return []
        rows=await (await conn.execute("SELECT * FROM passenger_requests WHERE notice_status='pending' AND (last_attempt_at IS NULL OR last_attempt_at<now()-interval '1 minute') ORDER BY submitted_at LIMIT 2")).fetchall()
        for row in rows:
            await conn.execute('UPDATE passenger_requests SET last_attempt_at=now() WHERE id=%s',(row['id'],))
            try:r=await bridge('POST','/send-alert',{'event_id':row['event_id'],'delivery_id':digest('passenger-response:'+str(row['id'])),'text':row['notice']})
            except HTTPException:results.append('pending');continue
            state=r.get('status','unknown')
            if state not in ('pending','sent','unknown','paused'):state='unknown'
            await conn.execute('UPDATE passenger_requests SET notice_status=%s WHERE id=%s',(state,row['id']))
            results.append(state)
    return results


def install_admin(app,operator):
    @app.post('/api/whatsapp/events/{event_id}/request')
    async def create(event_id:str,b:Version,actor=Depends(operator)):return await issue(event_id,b,actor)
    @app.post('/api/whatsapp/events/{event_id}/request/{request_id}/apply')
    async def review(event_id:str,request_id:UUID,b:Version,actor=Depends(operator)):
        return await apply_response(event_id,request_id,b,actor)
    @app.post('/api/whatsapp/events/{event_id}/request/{request_id}/revoke')
    async def revoke(event_id:str,request_id:UUID,actor=Depends(operator)):
        async with connection() as conn:
            # Never discard received answers through a revoke action.
            row=await (await conn.execute("UPDATE passenger_requests SET status='revoked' WHERE id=%s AND event_id=%s AND status='awaiting' RETURNING enquiry_id",(request_id,event_id))).fetchone()
            if row:await audit(conn,actor,'revoke_passenger_link','enquiry',row['enquiry_id'],{'request_id':str(request_id)})
        return {'ok':bool(row)}


rates=deque()
async def public_guard(request:Request):
    if not enabled():raise HTTPException(503,'Formulario no disponible')
    # This application runs one worker. Bounded global limiter; no untrusted forwarded IPs.
    now=time.monotonic()
    while rates and rates[0]<now-60:rates.popleft()
    if len(rates)>=120:raise HTTPException(429,'Muchas solicitudes. Esperá un minuto.')
    rates.append(now)
    if request.method=='POST' and request.headers.get('origin') not in (None,base_url()):
        raise HTTPException(403,'Origen no permitido')


def headers():return {'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",'X-Robots-Tag':'noindex, nofollow'}

@router.get('/solicitud',dependencies=[Depends(public_guard)])
async def page():return HTMLResponse(Path(__file__).with_name('passenger_form.html').read_text(),headers=headers())
@router.get('/solicitud/form.js',dependencies=[Depends(public_guard)])
async def script():return Response(Path(__file__).with_name('passenger_form.js').read_text(),media_type='text/javascript',headers=headers())
@router.get('/solicitud/form.css',dependencies=[Depends(public_guard)])
async def style():return Response(Path(__file__).with_name('passenger_form.css').read_text(),media_type='text/css',headers=headers())
@router.post('/solicitud/read',dependencies=[Depends(public_guard)])
async def read(b:Token):
    try:return JSONResponse(jsonable_encoder(await read_form(b.token)),headers=headers())
    except HTTPException:raise
    except Exception:raise HTTPException(503,'No se pudo abrir el formulario. Intentá más tarde.') from None
@router.post('/solicitud/submit',dependencies=[Depends(public_guard)])
async def submit(b:Submission):
    try:return JSONResponse(await submit_form(b),headers=headers())
    except HTTPException:raise
    except Exception:raise HTTPException(503,'No se pudo guardar. Conservá esta página abierta e intentá nuevamente.') from None
