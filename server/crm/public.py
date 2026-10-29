"""No public read endpoint for customers, enquiries, or commercial metrics."""
import time
from collections import deque
from fastapi import APIRouter, HTTPException
from crm.db import enabled
from crm.models import EnquiryInput
from crm.service import capture

router=APIRouter()
requests=deque()


@router.get('/crm/status')
async def status():
    return {'enabled':enabled()}


@router.post('/enquiries',status_code=201)
async def create(body:EnquiryInput):
    if not enabled(): raise HTTPException(503,'Registro de consultas no habilitado')
    now=time.monotonic()
    while requests and requests[0]<now-60: requests.popleft()
    if len(requests)>=20: raise HTTPException(429,'Muchas consultas; intentá nuevamente en un minuto')
    requests.append(now)
    try:
        return await capture(body)
    except HTTPException: raise
    except Exception:
        raise HTTPException(503,'No se pudo registrar la consulta. Podés continuar por WhatsApp.') from None
