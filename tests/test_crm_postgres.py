"""Integration tests: opt in only against the disposable roma_crm_test database."""
import os
from pathlib import Path
import sys
import unittest
from uuid import uuid4, UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from crm import service
from crm.db import connection
from crm.models import EnquiryInput, EnquiryUpdate, CatalogInput, CatalogUpdate
from crm.migrate import migrate


@unittest.skipUnless(os.getenv('CRM_TEST_DATABASE')=='true' and os.getenv('PGDATABASE')=='roma_crm_test','Requires isolated PostgreSQL test database')
class PostgreSQLIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_full_commercial_flow(self):
        await migrate()
        await migrate()  # repeated deploy must be idempotent
        request=EnquiryInput(request_id=uuid4(),summary='Consulta de prueba sobre traslado y alojamiento',categories=['transfer','alojamiento_yala'],consent=True)
        first=await service.capture(request)
        again=await service.capture(request)
        self.assertTrue(first['created'])
        self.assertFalse(again['created'])
        self.assertEqual(first['code'],again['code'])
        async with connection() as conn:
            row=await (await conn.execute('SELECT id,version FROM enquiries WHERE request_id=%s',(request.request_id,))).fetchone()
            events=await (await conn.execute('SELECT count(*) n FROM automation_events WHERE entity_id=%s',(row['id'],))).fetchone()
            self.assertEqual(events['n'],1)
        updated=await service.update_enquiry(row['id'],EnquiryUpdate(version=1,status='contactada',owner='Operador QA',next_action='Cotizar',categories=['transfer']), 'qa')
        self.assertEqual(updated['version'],2)
        metrics=await service.dashboard()
        self.assertGreaterEqual(metrics['totals']['total'],1)
        self.assertTrue(any(c['code']=='transfer' and c['total']>=1 for c in metrics['categories']))
        draft=await service.create_catalog(CatalogInput(title='Transfer QA',content='Traslado de prueba; confirmar disponibilidad',permanent=True), 'qa')
        await service.update_catalog(draft['id'],CatalogUpdate(title='Transfer QA',content='Traslado de prueba; confirmar disponibilidad',permanent=True,status='aprobado',version=1),'qa')
        context=await service.catalog_context()
        self.assertIn('Transfer QA',context)
        batch=await service.claim_events()
        self.assertTrue(batch['events'])
        self.assertFalse((await service.claim_events())['events'])
        event=next(e for e in batch['events'] if e['entity_id']==row['id'])
        self.assertTrue((await service.acknowledge(event['id'],UUID(batch['lease_token'])))['ok'])


if __name__=='__main__':unittest.main()
