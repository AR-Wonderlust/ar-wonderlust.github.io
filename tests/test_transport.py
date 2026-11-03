import unittest,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from crm.transport import QuoteInput,RateInput,calculate

class TransportTests(unittest.TestCase):
 def setUp(self):
  self.rates={'rates':[{'service':'traslado','yellow_standard':1150,'red_floor':921,'green_reference':1450}]}
  self.data=dict(request_id='00000000-0000-4000-8000-000000000001',enquiry_id=1,rate_id=1,valid_until='2027-11-01',conditions='Incluye chofer y combustible',legs=[dict(service='traslado',travel_date='2027-11-02',origin='JUJ',destination='Purmamarca',vehicle='Hiace',passengers=4,capacity=13,operational_km=192,km_confirmed=True)])
 def test_price_vehicle_not_passenger(self):
  self.assertEqual(calculate(QuoteInput(**self.data),self.rates)['total'],'220800.00')
  self.data['legs'][0]['passengers']=12
  self.assertEqual(calculate(QuoteInput(**self.data),self.rates)['total'],'220800.00')
 def test_floor_and_green_blocked(self):
  for price in [920,1450]:
   self.data['legs'][0]['negotiated_rate']=price
   with self.assertRaises(ValueError):calculate(QuoteInput(**self.data),self.rates)
 def test_discount(self):
  self.data['legs'][0]['negotiated_rate']=921
  with self.assertRaises(ValueError):calculate(QuoteInput(**self.data),self.rates)
  self.data.update(multiple_trips=True,discount_reason='Tres salidas')
  self.assertEqual(calculate(QuoteInput(**self.data),self.rates)['total'],'176832.00')
 def test_incomplete_and_capacity(self):
  self.data['legs'][0].update(km_confirmed=False,capacity=3)
  self.assertEqual(len(calculate(QuoteInput(**self.data),self.rates)['blockers']),2)
 def test_per_vehicle_legs_and_extras(self):
  self.data['legs']*=2
  self.data.update(extras_amount='150.25',extras_description='Peajes')
  self.assertEqual(calculate(QuoteInput(**self.data),self.rates)['total'],'441750.25')
 def test_invalid_numbers(self):
  for km in ['NaN','Infinity',0,-1]:
   self.data['legs'][0]['operational_km']=km
   with self.assertRaises(ValueError):QuoteInput(**self.data)
 def test_rates(self):
  data=dict(source=dict(spreadsheet_id='1W55J03Uy1sY15Wj649_JDslyg1vCiBNHDpB5pvjTMS8',sheet='TRANSPORTE-ROMA-2026',range='E1:N3',read_at=datetime.now(timezone.utc)),rates=[dict(service=s,green_reference=1450,yellow_standard=1150,red_floor=921) for s in ['traslado','auto','excursion']])
  RateInput(**data)
  data['rates'][2]['service']='auto'
  with self.assertRaises(ValueError):RateInput(**data)

if __name__=='__main__':unittest.main()

import os
from unittest.mock import patch
import httpx
from crm.admin import app
class TransportAuth(unittest.IsolatedAsyncioTestCase):
 async def test_protected_routes(self):
  with patch.dict(os.environ,{'CRM_ADMIN_USER':'operator','CRM_ADMIN_PASSWORD':'x'*32,'CRM_AUTOMATION_TOKEN':'t'*40}):
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
    for path in ['/presupuestos','/transport.js','/api/transport/rates','/api/transport/quotes']:
     self.assertEqual((await client.get(path)).status_code,401)
    self.assertEqual((await client.get('/presupuestos',auth=('operator','x'*32))).status_code,200)
    self.assertEqual((await client.post('/automation/transport/rates',json={})).status_code,401)
    self.assertEqual((await client.post('/api/transport/quotes',json={},auth=('operator','x'*32))).status_code,403)
    self.assertEqual((await client.post('/api/transport/quotes/1/approve',headers={'X-ROMA-Panel':'1'},auth=('operator','x'*32),json={'availability_confirmed':False,'capacity_and_baggage_confirmed':True,'tariff_validity_confirmed':True,'extras_confirmed':True})).status_code,422)
