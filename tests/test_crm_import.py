import asyncio
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from crm.drive_import import extract, download


class ImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_plain_text_always_pending_and_undated(self):
        draft=await extract(None,{'name':'Flyer','mimeType':'text/plain'},b'Salida 14 de noviembre. Consultar precio.')
        self.assertIsNone(draft.starts_on)
        self.assertFalse(draft.permanent)
        self.assertIn('PENDIENTE',draft.content)

    async def test_docs_flags_missing_embedded_images(self):
        draft=await extract(None,{'name':'Flyers','mimeType':'application/vnd.google-apps.document'},b'Actividades')
        self.assertIn('no incluye imágenes',draft.content)

    async def test_no_silent_truncation(self):
        with self.assertRaises(ValueError):
            await extract(None,{'name':'Largo','mimeType':'text/plain'},b'x'*19001)

    async def test_empty_export_is_not_a_valid_draft(self):
        with self.assertRaises(ValueError):
            await extract(None,{'name':'Vacio','mimeType':'text/plain'},b'  ')


if __name__=='__main__': unittest.main()
