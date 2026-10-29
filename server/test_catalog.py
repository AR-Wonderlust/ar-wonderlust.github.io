"""Offline regression checks for catalog limits; no credentials or API calls."""
import ast
import asyncio
import os
from pathlib import Path
import re
import time
import types
import unittest
from unittest.mock import patch


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Response:
    encoding = 'utf-8'
    def __init__(self, data=b'', files=None):
        self.data, self.files = data, files
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def raise_for_status(self): pass
    def json(self): return {'files': self.files}
    async def aiter_bytes(self, chunk_size):
        for i in range(0, len(self.data), chunk_size):
            yield self.data[i:i+chunk_size]


class Client:
    def __init__(self, files, payload):
        self.files, self.payload, self.requests = files, payload, []
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def get(self, *args, **kwargs): return Response(files=self.files)
    def stream(self, method, url, **kwargs):
        self.requests.append((url, kwargs['params']))
        return Response(self.payload)


class CatalogLimits(unittest.IsolatedAsyncioTestCase):
    def setup_catalog(self, size='1003962', mime='application/vnd.google-apps.document', payload=b'Excursiones disponibles', count=1):
        files = [{'id': str(i), 'name': 'Actividad', 'mimeType': mime, 'size': size} for i in range(count)]
        client = Client(files, payload)
        async def headers(): return {}
        ns = {'asyncio': asyncio, 'os': os, 're': re, 'time': time,
              'HTTPException': HTTPException, 'drive_headers': headers,
              'lock': asyncio.Lock(), 'cache': {'text': '', 'expires': 0},
              'httpx': types.SimpleNamespace(AsyncClient=lambda **kw: client)}
        tree = ast.parse(Path(__file__).with_name('app.py').read_text())
        functions = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name in ('catalog', 'read_catalog_document')]
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'app.py', 'exec'), ns)
        return ns, client

    async def run_catalog(self, ns):
        with patch.dict(os.environ, {'DRIVE_FOLDER_ID': 'test-folder'}):
            return await ns['catalog']()

    async def test_large_docs_storage_small_export_succeeds(self):
        ns, client = self.setup_catalog()
        result = await self.run_catalog(ns)
        self.assertIn('Excursiones disponibles', result)
        self.assertTrue(client.requests[0][0].endswith('/export'))
        self.assertEqual(client.requests[0][1], {'mimeType': 'text/plain'})

    async def test_exact_byte_limit_allowed(self):
        ns, client = self.setup_catalog(payload=('中'*66666+'ab').encode())
        text = await ns['read_catalog_document'](client, client.files[0], {})
        self.assertEqual(len(text.encode()), 200000)

    async def test_oversized_export_or_text_rejected_even_with_small_metadata(self):
        for mime in ('application/vnd.google-apps.document', 'text/plain'):
            ns, client = self.setup_catalog(size='1', mime=mime, payload=b'x'*200001)
            with self.assertRaises(HTTPException) as error:
                await self.run_catalog(ns)
            self.assertIn('Texto de un documento', error.exception.detail)
            self.assertEqual(ns['cache']['expires'], 0)

    async def test_combined_character_limit_preserved(self):
        ns, _ = self.setup_catalog(payload=b'x'*60001, count=2)
        with self.assertRaises(HTTPException) as error:
            await self.run_catalog(ns)
        self.assertEqual(error.exception.detail, 'Catálogo demasiado grande.')
        self.assertEqual(ns['cache']['expires'], 0)

    async def test_document_count_limit_preserved(self):
        ns, _ = self.setup_catalog(count=51)
        with self.assertRaises(HTTPException):
            await self.run_catalog(ns)
        self.assertEqual(ns['cache']['expires'], 0)


if __name__ == '__main__':
    unittest.main()
