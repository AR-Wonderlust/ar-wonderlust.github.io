"""Run only on the loopback/VPN service. Never route Cloudflare Tunnel here."""
import os
import secrets
from pathlib import Path
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import psycopg
from crm import service
from crm.models import EnquiryUpdate, CatalogInput, CatalogUpdate
from crm.db import connection

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
basic=HTTPBasic(auto_error=False)
bearer=HTTPBearer(auto_error=False)


def operator(credentials:HTTPBasicCredentials|None=Depends(basic)):
    user=os.getenv('CRM_ADMIN_USER','')
    password=os.getenv('CRM_ADMIN_PASSWORD','')
    if not user or len(password)<24: raise HTTPException(503,'Configurar credenciales del panel')
    if not credentials or not (secrets.compare_digest(credentials.username.encode(),user.encode()) & secrets.compare_digest(credentials.password.encode(),password.encode())):
        raise HTTPException(401,'Ingreso requerido',headers={'WWW-Authenticate':'Basic realm="ROMA privado"'})
    return user


def automation(credentials:HTTPAuthorizationCredentials|None=Depends(bearer)):
    token=os.getenv('CRM_AUTOMATION_TOKEN','')
    if len(token)<32: raise HTTPException(503,'Automatización no configurada')
    if not credentials or not secrets.compare_digest(credentials.credentials,token): raise HTTPException(401,'No autorizado')


@app.middleware('http')
async def hardening(request:Request,call_next):
    # Custom header prevents cross-origin form submissions with cached Basic credentials.
    if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD'):
        if request.headers.get('x-roma-panel')!='1': return JSONResponse({'detail':'Solicitud no permitida'},403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


@app.exception_handler(psycopg.Error)
async def database_error(request,exc):
    return JSONResponse({'detail':'Base de datos no disponible o dato incompatible. Revisá el estado del servicio.'},503)


@app.get('/',response_class=HTMLResponse,dependencies=[Depends(operator)])
async def panel(): return Path(__file__).with_name('panel.html').read_text()


@app.get('/panel.js',dependencies=[Depends(operator)])
async def script():
    from fastapi.responses import Response
    return Response(Path(__file__).with_name('panel.js').read_text(),media_type='text/javascript')


@app.get('/api/metrics',dependencies=[Depends(operator)])
async def metrics(): return await service.dashboard()


@app.get('/api/categories',dependencies=[Depends(operator)])
async def categories():
    async with connection() as conn:
        return await (await conn.execute('SELECT code,name FROM categories WHERE active ORDER BY name')).fetchall()


@app.get('/api/enquiries',dependencies=[Depends(operator)])
async def enquiries(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    return await service.list_enquiries(limit,offset)


@app.patch('/api/enquiries/{enquiry_id}')
async def update(enquiry_id:int,body:EnquiryUpdate,actor=Depends(operator)):
    return await service.update_enquiry(enquiry_id,body,actor)


@app.get('/api/catalog',dependencies=[Depends(operator)])
async def catalog(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    return await service.list_catalog(limit,offset)


@app.post('/api/catalog',status_code=201)
async def create_catalog(body:CatalogInput,actor=Depends(operator)):
    return await service.create_catalog(body,actor)


@app.patch('/api/catalog/{item_id}')
async def edit_catalog(item_id:int,body:CatalogUpdate,actor=Depends(operator)):
    return await service.update_catalog(item_id,body,actor)


@app.post('/automation/events/claim',dependencies=[Depends(automation)])
async def claim(): return await service.claim_events()


class Ack(BaseModel):
    lease_token:UUID


@app.post('/automation/events/{event_id}/ack',dependencies=[Depends(automation)])
async def ack(event_id:int,body:Ack): return await service.acknowledge(event_id,body.lease_token)
