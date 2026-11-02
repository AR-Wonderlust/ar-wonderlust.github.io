import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4
from hashlib import sha256
from unittest.mock import patch, AsyncMock
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from crm import whatsapp as wa
from crm.admin import app
from crm.db import connection
from crm.migrate import migrate


class WhatsAppRules(unittest.TestCase):
    def test_templates_and_ambiguous_messages(self):
        kind,category,draft=wa.classify('Necesito traslado desde el aeropuerto para 4 personas')
        self.assertEqual((kind,category),('posible_consulta','transfer'))
        self.assertIn('sujetas a confirmación',draft)
        self.assertEqual(wa.classify('Ofrecemos alojamiento en Yala')[0],'oferta')
        self.assertEqual(wa.classify('Buen día, gracias')[0],'irrelevante')
        self.assertEqual(wa.classify('Busco excursión a Salinas')[1],'actividad')
        self.assertEqual(wa.classify('Busco alquiler de vehículo')[1],'alquiler_vehiculo')


class WhatsAppAccess(unittest.IsolatedAsyncioTestCase):
    async def test_credentials_separated_and_csrf_required(self):
        with patch.dict(os.environ,{'CRM_ADMIN_USER':'roma','CRM_ADMIN_PASSWORD':'a'*32,'CRM_AUTOMATION_TOKEN':'b'*40,'WA_BRIDGE_TOKEN':'c'*40}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://private') as c:
                self.assertEqual((await c.get('/whatsapp')).status_code,401)
                self.assertEqual((await c.get('/whatsapp',auth=('roma','a'*32))).status_code,200)
                self.assertEqual((await c.post('/api/whatsapp/process',auth=('roma','a'*32))).status_code,403)
                for token in ['b'*40,'a'*32]:
                    r=await c.post('/integrations/whatsapp/events',json={},headers={'Authorization':'Bearer '+token})
                    self.assertEqual(r.status_code,401)
                self.assertEqual((await c.post('/automation/whatsapp/run',headers={'Authorization':'Bearer '+'c'*40})).status_code,401)
                with patch('crm.whatsapp.process_batch',AsyncMock(return_value=0)),patch('crm.whatsapp.dispatch_batch',AsyncMock(return_value=[])),patch('crm.whatsapp.dispatch_responses',AsyncMock(return_value=[])):
                    self.assertEqual((await c.post('/automation/whatsapp/run',headers={'Authorization':'Bearer '+'b'*40})).status_code,200)


@unittest.skipUnless(os.getenv('CRM_TEST_DATABASE')=='true' and os.getenv('PGDATABASE')=='roma_crm_test','Requires isolated PostgreSQL test database')
class WhatsAppPostgres(unittest.IsolatedAsyncioTestCase):
    async def test_capture_process_and_uncertain_delivery_are_idempotent(self):
        await migrate()
        event=wa.Event(event_id=sha256(str(uuid4()).encode()).hexdigest(),account_id=uuid4(),group_id='123@g.us',group_name='QA interno',sender_id='opaque@lid',message_id=str(uuid4()),text='Busco transfer al aeropuerto',timestamp=1793577600)
        self.assertTrue((await wa.receive(event))['created'])
        self.assertFalse((await wa.receive(event))['created'])
        await wa.process_batch();await wa.process_batch()
        async with connection() as conn:
            row=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s',(event.event_id,))).fetchone()
            self.assertEqual(row['classification'],'posible_consulta')
            self.assertIsNotNone(row['enquiry_id'])
            enquiry=await (await conn.execute('SELECT * FROM enquiries WHERE id=%s',(row['enquiry_id'],))).fetchone()
            self.assertEqual(enquiry['channel'],'whatsapp')
            self.assertEqual(enquiry['contact'],'')
            self.assertIn(event.text,enquiry['summary'])
        with patch('crm.whatsapp.bridge',AsyncMock(return_value={'status':'unknown'})) as mocked:
            await wa.dispatch_batch();await wa.dispatch_batch()
            relevant=[c for c in mocked.call_args_list if c.args[2]['event_id']==event.event_id]
            self.assertEqual(len(relevant),1)
        async with connection() as conn:
            row=await (await conn.execute('SELECT delivery_status FROM whatsapp_events WHERE event_id=%s',(event.event_id,))).fetchone()
            self.assertEqual(row['delivery_status'],'unknown')


if __name__=='__main__':unittest.main()
