import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from hashlib import sha256
from unittest.mock import patch
from pydantic import ValidationError
from fastapi import HTTPException
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from crm.whatsapp_ficha import Ficha, extract, missing, draft_for
from crm import whatsapp as wa
from crm.db import connection
from crm.migrate import migrate
AT=datetime.fromisoformat('2026-11-02T15:00:00+00:00')


class FichaExtraction(unittest.TestCase):
    def test_real_transfer_does_not_repeat_known_passengers(self):
        f=extract('Necesito un transfer desde el aeropuerto para cuatro personas el viernes',AT,'transfer')
        self.assertEqual(f.passengers,4)
        self.assertEqual(f.travel_date,date(2026,11,6))
        self.assertFalse(f.date_confirmed)
        self.assertIn('origin',[v['field'] for v in missing(f)])
        draft=draft_for(f)
        self.assertNotIn('¿Cuántas personas',draft)
        self.assertIn('06/11/2026',draft)

    def test_explicit_route_and_time(self):
        f=extract('Busco transfer desde aeropuerto de Salta a Yala para 4 personas el 06/11/2026 a las 14:30',AT,'transfer')
        self.assertEqual((f.origin,f.destination,f.time),('aeropuerto de Salta','Yala','14:30'))
        f.date_confirmed=True;f.luggage='Dos valijas'
        self.assertEqual(missing(f),[])
        self.assertNotIn('¿',draft_for(f))
        f.extra_question='¿Necesitan una silla infantil?'
        self.assertIn(f.extra_question,draft_for(f))

    def test_timezone_and_ambiguous_dates(self):
        # UTC Monday is still Sunday in Jujuy. Tomorrow must mean Monday.
        f=extract('Necesito transfer mañana',datetime.fromisoformat('2026-11-02T01:00:00+00:00'),'transfer')
        self.assertEqual(f.travel_date,date(2026,11,2))
        for text in ['viernes o sábado','el viernes pasado','cada viernes','31/02/2026','por la mañana']:
            self.assertIsNone(extract(text,AT).travel_date,text)
        self.assertEqual(extract('el 02/01',AT).travel_date,date(2027,1,2))
        self.assertIn('no coincide',extract('viernes 05/11/2026',AT).notes)

    def test_date_range_and_short_route(self):
        f=extract('Busco alojamiento del 30/12/2026 al 02/01/2027',AT,'alojamiento_yala')
        self.assertEqual((f.travel_date,f.end_date),(date(2026,12,30),date(2027,1,2)))
        f=extract('Transfer de Salta a Yala para 4 personas',AT,'transfer')
        self.assertEqual((f.origin,f.destination),('Salta','Yala'))
        self.assertEqual(extract('somos cuatro',AT).passengers,4)

    def test_passengers_not_flight_numbers_and_conflicts(self):
        self.assertIsNone(extract('Vuelo AR1234 a las 14:30',AT).passengers)
        self.assertIsNone(extract('somos 4 personas o 6 personas',AT).passengers)
        self.assertEqual(extract('dos adultos y tres niños',AT).passengers,5)

    def test_validation_and_contact_link(self):
        for data in [{'phone':'123456789@lid'}, {'phone':'javascript:alert(1)'}, {'time':'28:00'}, {'passengers':0}, {'travel_date':'2026-11-06','end_date':'2026-11-05'}, {'contact_confirmed':True}]:
            with self.assertRaises(ValidationError):Ficha(**data)
        f=Ficha(phone='+5493881234567')
        self.assertEqual(wa.ficha_result(f,'Hola')['whatsapp_url'],'')
        f.contact_confirmed=True
        self.assertEqual(wa.ficha_result(f,'Hola & gracias')['whatsapp_url'],'https://wa.me/5493881234567?text=Hola+%26+gracias')


@unittest.skipUnless(os.getenv('CRM_TEST_DATABASE')=='true' and os.getenv('PGDATABASE')=='roma_crm_test','Requires isolated PostgreSQL test database')
class FichaPostgres(unittest.IsolatedAsyncioTestCase):
    async def test_saved_draft_contact_and_crm_sync_with_conflicts(self):
        await migrate()
        event=wa.Event(event_id=sha256(str(uuid4()).encode()).hexdigest(),account_id=uuid4(),group_id='123@g.us',group_name='QA',sender_id='opaque@lid',sender_name='QA Autor',sender_phone='+5493881234567',phone_source='participant_alt',message_id=str(uuid4()),text='Necesito transfer para cuatro personas el viernes',timestamp=AT.timestamp())
        await wa.receive(event);await wa.process_batch()
        async with connection() as conn:
            row=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s',(event.event_id,))).fetchone()
            enquiry=await (await conn.execute('SELECT * FROM enquiries WHERE id=%s',(row['enquiry_id'],))).fetchone()
        self.assertEqual(row['sender_phone'],event.sender_phone)
        self.assertEqual(enquiry['passengers'],4)
        self.assertIsNone(enquiry['travel_start'])  # proposed is not confirmed
        f=Ficha(**row['ficha']);f.date_confirmed=True;f.contact_confirmed=True
        f.destination='Yala';f.extra_question='¿Nos pasás el número de vuelo?'
        save=wa.FichaSave(version=row['ficha_version'],enquiry_version=enquiry['version'],ficha=f,draft='Respuesta editada por el operador')
        with patch('crm.whatsapp.bridge',side_effect=AssertionError('Saving must not send')):
            result=await wa.save_ficha(event.event_id,save,'qa')
        self.assertTrue(result['whatsapp_url'].startswith('https://wa.me/5493881234567?'))
        with self.assertRaises(HTTPException) as error:await wa.save_ficha(event.event_id,save,'qa')
        self.assertEqual(error.exception.status_code,409)
        async with connection() as conn:
            updated=await (await conn.execute('SELECT * FROM whatsapp_events WHERE event_id=%s',(event.event_id,))).fetchone()
            enquiry=await (await conn.execute('SELECT * FROM enquiries WHERE id=%s',(row['enquiry_id'],))).fetchone()
        self.assertEqual(updated['draft'],'Respuesta editada por el operador')
        self.assertEqual(updated['notice'],row['notice'])  # stable deduplication payload
        self.assertEqual(updated['delivery_status'],row['delivery_status'])
        self.assertEqual(enquiry['travel_start'],date(2026,11,6))
        self.assertEqual(enquiry['contact'],event.sender_phone)
        # Concurrent changes in the main CRM panel must not be overwritten silently.
        async with connection() as conn:await conn.execute('UPDATE enquiries SET version=version+1 WHERE id=%s',(row['enquiry_id'],))
        save.version=result['ficha_version'];save.enquiry_version=result['enquiry_version']
        with self.assertRaises(HTTPException) as error:await wa.save_ficha(event.event_id,save,'qa')
        self.assertEqual(error.exception.status_code,409)
