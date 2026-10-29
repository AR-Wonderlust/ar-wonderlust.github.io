import asyncio
from contextlib import asynccontextmanager
from datetime import date
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import httpx
from fastapi import FastAPI
from pydantic import ValidationError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from crm.admin import app as admin
from crm.public import router, requests
from crm.models import EnquiryInput, CatalogUpdate
from crm import service

public=FastAPI()
public.include_router(router)


class ModelTests(unittest.TestCase):
    def test_consent_required(self):
        for consent in [False,None]:
            with self.assertRaises(ValidationError):
                EnquiryInput(request_id=uuid4(),summary='Viaje',consent=consent)

    def test_validations(self):
        with self.assertRaises(ValidationError):
            EnquiryInput(request_id=uuid4(),summary='Viaje',consent=True,travel_start='2026-11-02',travel_end='2026-11-01')
        with self.assertRaises(ValidationError):
            EnquiryInput(request_id=uuid4(),summary='Viaje',consent=True,categories=['inventada'])
        with self.assertRaises(ValidationError):
            CatalogUpdate(title='Flyer',content='Datos',status='aprobado',version=1)
        approved=CatalogUpdate(title='Transfer',content='Consultar',permanent=True,status='aprobado',version=1)
        self.assertTrue(approved.permanent)


class AccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env=patch.dict(os.environ,{'CRM_ADMIN_USER':'roma','CRM_ADMIN_PASSWORD':'a'*32,'CRM_AUTOMATION_TOKEN':'b'*40,'CRM_ENABLED':'true'})
        self.env.start()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=admin),base_url='http://private')
        requests.clear()

    async def asyncTearDown(self):
        await self.client.aclose()
        self.env.stop()

    async def test_panel_requires_auth_and_has_security_headers(self):
        r=await self.client.get('/')
        self.assertEqual(r.status_code,401)
        r=await self.client.get('/',auth=('roma','a'*32))
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertEqual(r.headers['x-frame-options'],'DENY')

    async def test_no_cross_origin_write(self):
        r=await self.client.post('/api/catalog',auth=('roma','a'*32),json={'title':'x','content':'y'})
        self.assertEqual(r.status_code,403)

    async def test_bearer_and_basic_are_not_interchangeable(self):
        r=await self.client.get('/api/metrics',headers={'Authorization':'Bearer '+'b'*40})
        self.assertEqual(r.status_code,401)
        r=await self.client.post('/automation/events/claim',auth=('roma','a'*32))
        self.assertEqual(r.status_code,401)

    async def test_public_has_no_private_read_routes(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=public),base_url='http://public') as c:
            for path in ['/api/metrics','/api/enquiries','/automation/events/claim']:
                self.assertEqual((await c.get(path)).status_code,404)

    async def test_public_failure_does_not_leak_database_details(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=public),base_url='http://public') as c:
            with patch('crm.public.capture',side_effect=RuntimeError('password=secret')):
                r=await c.post('/enquiries',json={'request_id':str(uuid4()),'summary':'Viaje','consent':True})
            self.assertEqual(r.status_code,503)
            self.assertNotIn('secret',r.text)

    async def test_public_disabled_is_explicit(self):
        with patch.dict(os.environ,{'CRM_ENABLED':'false'}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=public),base_url='http://public') as c:
                self.assertFalse((await c.get('/crm/status')).json()['enabled'])
                r=await c.post('/enquiries',json={'request_id':str(uuid4()),'summary':'Viaje','consent':True})
                self.assertEqual(r.status_code,503)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_idempotent_retry_does_not_emit_second_event(self):
        class Cursor:
            def __init__(self,row):self.row=row
            async def fetchone(self):return self.row
        queries=[]
        class Connection:
            async def execute(self,query,args):
                queries.append(query)
                return Cursor(None if query.startswith('INSERT') else {'id':1,'code':'CON-00000001'})
        @asynccontextmanager
        async def connection():yield Connection()
        with patch('crm.service.connection',connection):
            result=await service.capture(EnquiryInput(request_id=uuid4(),summary='Viaje',consent=True))
        self.assertEqual(result,{'code':'CON-00000001','created':False})
        self.assertEqual(len(queries),2)
        self.assertFalse(any('automation_events' in q for q in queries))


if __name__=='__main__':unittest.main()
