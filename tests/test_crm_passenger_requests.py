import os
import sys
import unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from hashlib import sha256
from unittest.mock import patch,AsyncMock
import httpx
from fastapi import HTTPException
from pydantic import ValidationError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from crm import passenger_requests as pr, whatsapp as wa
from crm.whatsapp_filter import classify_message
from crm.db import connection
from crm.migrate import migrate
from crm.admin import app as private
import app as public_app


class TourismFilter(unittest.TestCase):
    def test_questions_need_tourism_context(self):
        for text in ['¿Alguien sabe dónde alojarse en Yala?', '¿Cuánto alquilan una camioneta?', '¿Dónde alquilan cabañas?', '¿Cómo llego a Purmamarca?', 'Necesito transfer desde el aeropuerto', '¿Alguien conoce un hotel en Tilcara?']:
            self.assertEqual(classify_message(text)[0],'posible_consulta',text)
        for text in ['Cuánto cobrará un psicólogo para acomodar las ideas', '¿Alguien sabe arreglar una heladera?', '¿Dónde alquilan herramientas?', 'Buen día, buena semana', 'Alguien sabe?', 'Ofrecemos traslados, consultas al teléfono']:
            self.assertNotEqual(classify_message(text)[0],'posible_consulta',text)

    def test_passenger_cannot_set_internal_fields(self):
        with self.assertRaises(ValidationError):pr.PassengerDetails(name='QA',passengers=4,consent=True,category='transfer',contact_confirmed=True)
        with self.assertRaises(ValidationError):pr.PassengerDetails(name='QA',passengers=4,consent=False)
        with self.assertRaises(ValidationError):pr.PassengerDetails(name='QA',passengers=4,consent=True,time='25:00')


class FormAccess(unittest.IsolatedAsyncioTestCase):
    async def test_real_app_public_page_and_scoped_reads(self):
        pr.rates.clear()
        with patch.dict(os.environ,{'CRM_ENABLED':'true','CRM_PUBLIC_BASE_URL':'https://asistente.romanomad.travel'}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=public_app.app),base_url='https://asistente.romanomad.travel') as client:
                response=await client.get('/solicitud')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['referrer-policy'],'no-referrer')
                self.assertEqual(response.headers['cache-control'],'no-store')
                self.assertIn('frame-ancestors',response.headers['content-security-policy'])
                self.assertEqual((await client.get('/solicitud/form.js')).status_code,200)
                self.assertEqual((await client.get('/solicitud/form.css')).status_code,200)
                with patch('crm.passenger_requests.read_form',AsyncMock(return_value={'submitted':False,'fields':{'name':'QA'},'expires_at':datetime.now(timezone.utc)})):
                    r=await client.post('/solicitud/read',json={'token':'A'*43},headers={'Origin':'https://asistente.romanomad.travel'})
                    self.assertEqual(r.status_code,200)
                    self.assertIn('expires_at',r.json())
                    self.assertEqual((await client.post('/solicitud/read',json={'token':'A'*43},headers={'Origin':'https://evil.example'})).status_code,403)
                self.assertEqual((await client.post('/solicitud/read',json={'token':'bad'})).status_code,422)
                self.assertEqual((await client.post('/solicitud/submit',content='x'*25000)).status_code,413)
                self.assertEqual((await client.get('/api/whatsapp/events',headers={'Origin':public_app.origin})).status_code,404)

    async def test_private_controls_need_auth_and_csrf(self):
        with patch.dict(os.environ,{'CRM_ADMIN_USER':'roma','CRM_ADMIN_PASSWORD':'a'*32}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=private),base_url='http://private') as c:
                for path in ['/api/whatsapp/events/abc/request','/api/whatsapp/events/abc/promote']:
                    self.assertEqual((await c.post(path,headers={'X-ROMA-Panel':'1'},json={'version':1,'enquiry_version':1})).status_code,401)
                    self.assertEqual((await c.post(path,auth=('roma','a'*32),json={'version':1,'enquiry_version':1})).status_code,403)


@unittest.skipUnless(os.getenv('CRM_TEST_DATABASE')=='true' and os.getenv('PGDATABASE')=='roma_crm_test','Requires isolated PostgreSQL test database')
class FormDatabase(unittest.IsolatedAsyncioTestCase):
    async def test_issue_expire_regenerate_submit_review_and_notify(self):
        await migrate()
        event=wa.Event(event_id=sha256(str(uuid4()).encode()).hexdigest(),account_id=uuid4(),group_id='123@g.us',group_name='Private group must never be public',sender_id='secret@lid',message_id=str(uuid4()),text='Necesito un transfer para cuatro personas el viernes',timestamp=datetime.now(timezone.utc).timestamp())
        await wa.receive(event);await wa.process_batch()
        async with connection() as conn:
            row=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s',(event.event_id,))).fetchone()
            e=await (await conn.execute('SELECT * FROM enquiries WHERE id=%s',(row['enquiry_id'],))).fetchone()
        version=pr.Version(version=row['ficha_version'],enquiry_version=e['version'])
        first=await pr.issue(event.event_id,version,'qa')
        first_token=first['url'].split('#')[1]
        async with connection() as conn:
            stored=await (await conn.execute('SELECT * FROM passenger_requests WHERE id=%s',(first['id'],))).fetchone()
            self.assertNotEqual(stored['token_hash'],first_token)
            self.assertEqual(stored['token_hash'],pr.digest(first_token))
        public=await pr.read_form(first_token)
        self.assertEqual(public['fields']['passengers'],4)
        for forbidden in ['group_name','sender_id','event_id','notes','contact_confirmed']:
            self.assertNotIn(forbidden,public['fields'])
        second=await pr.issue(event.event_id,version,'qa')
        with self.assertRaises(HTTPException) as error:await pr.read_form(first_token)
        self.assertEqual(error.exception.status_code,410)
        token=second['url'].split('#')[1]
        async with connection() as conn:await conn.execute("UPDATE passenger_requests SET expires_at=now()-interval '1 minute' WHERE id=%s",(second['id'],))
        with self.assertRaises(HTTPException):await pr.read_form(token)
        third=await pr.issue(event.event_id,version,'qa');token=third['url'].split('#')[1]
        body=pr.Submission(token=token,submission_id=uuid4(),details=pr.PassengerDetails(name='Passenger QA',phone='+5493881234567',passengers=5,origin='Aeropuerto de Salta',destination='Yala',travel_date='2026-12-20',answer='Una silla infantil',comments='Llevamos cochecito',consent=True))
        self.assertFalse((await pr.submit_form(body))['already_received'])
        self.assertTrue((await pr.submit_form(body))['already_received'])
        self.assertEqual(await pr.read_form(token),{'submitted':True})
        body.submission_id=uuid4()
        with self.assertRaises(HTTPException) as error:await pr.submit_form(body)
        self.assertEqual(error.exception.status_code,409)
        with self.assertRaises(HTTPException):await pr.issue(event.event_id,version,'qa')
        async with connection() as conn:
            e2=await (await conn.execute('SELECT passengers FROM enquiries WHERE id=%s',(row['enquiry_id'],))).fetchone()
        self.assertEqual(e2['passengers'],4)  # No automatic overwrite before human review.
        bridge=AsyncMock(return_value={'status':'sent'})
        await pr.dispatch_responses(bridge);await pr.dispatch_responses(bridge)
        calls=[c for c in bridge.call_args_list if c.args[2]['event_id']==event.event_id]
        self.assertEqual(len(calls),1)
        self.assertNotEqual(calls[0].args[2]['delivery_id'],event.event_id)
        self.assertNotIn(token,calls[0].args[2]['text'])
        await pr.apply_response(event.event_id,UUID(third['id']),version,'qa')
        async with connection() as conn:
            e3=await (await conn.execute('SELECT passengers,name FROM enquiries WHERE id=%s',(row['enquiry_id'],))).fetchone()
            request=await (await conn.execute('SELECT status,response FROM passenger_requests WHERE id=%s',(third['id'],))).fetchone()
        self.assertEqual(e3['passengers'],5)
        self.assertEqual(request['status'],'reviewed')
        self.assertEqual(request['response']['comments'],'Llevamos cochecito')

from uuid import UUID
