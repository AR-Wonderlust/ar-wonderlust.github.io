"""Public gallery limited to an explicitly selected Drive folder and four regions."""
import asyncio
import os
import re
import time
import httpx
from fastapi import HTTPException
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask

API = 'https://www.googleapis.com/drive/v3/files'
REGIONS = {'quebrada', 'puna', 'yungas', 'valles'}
TYPES = {'image/jpeg', 'image/png', 'image/webp', 'video/mp4'}
MAX_VIDEO = 25 * 1024 * 1024
MAX_IMAGE = 5 * 1024 * 1024


def media_entry(item, region):
    mime = item.get('mimeType')
    size = int(item.get('size', 0))
    if (mime not in TYPES or not re.fullmatch(r'[\w-]+', item.get('id', ''))
            or not item.get('capabilities', {}).get('canDownload', False)
            or not 0 < size <= (MAX_VIDEO if mime == 'video/mp4' else MAX_IMAGE)):
        return None
    return {'id': item['id'], 'region': region, 'kind': 'video' if mime == 'video/mp4' else 'image',
            'mime': mime, 'size': size, 'url': '/media/' + item['id']}


class Gallery:
    def __init__(self, get_headers):
        self.get_headers = get_headers
        self.lock = asyncio.Lock()
        self.slots = asyncio.Semaphore(6)
        self.items = {}
        self.expires = 0
        self.failed = False

    async def listing(self):
        async with self.lock:
            if time.monotonic() < self.expires:
                if self.failed:
                    raise HTTPException(503, 'Galería temporalmente no disponible')
                return list(self.items.values())
            folder = os.getenv('DRIVE_MEDIA_FOLDER_ID', '')
            if not folder:
                return []
            if not re.fullmatch(r'[\w-]+', folder):
                raise HTTPException(503, 'Carpeta de fotos no configurada')
            try:
                headers = await self.get_headers()
                async with httpx.AsyncClient(timeout=20) as client:
                    async def children(parent):
                        result, token = [], None
                        for _ in range(5):
                            params = {'q': f"'{parent}' in parents and trashed=false",
                                      'fields': 'nextPageToken,files(id,name,mimeType,size,capabilities(canDownload))',
                                      'pageSize': 100, 'orderBy': 'name'}
                            if token:
                                params['pageToken'] = token
                            res = await client.get(API, params=params, headers=headers)
                            res.raise_for_status()
                            data = res.json()
                            result.extend(data.get('files', []))
                            token = data.get('nextPageToken')
                            if not token:
                                return result
                        raise ValueError('Too many files')

                    root = await children(folder)
                    groups = [('general', root)]
                    for item in root:
                        if (item.get('mimeType') == 'application/vnd.google-apps.folder'
                                and item.get('name', '').strip().lower() in REGIONS):
                            groups.append((item['name'].strip().lower(), await children(item['id'])))
                    entries = []
                    for region, files in groups:
                        for item in files:
                            entry = media_entry(item, region)
                            if entry:
                                entries.append(entry)
                    if len(entries) > 200:
                        raise ValueError('Too many gallery items')
                self.items = {item['id']: item for item in entries}
                self.failed = False
                self.expires = time.monotonic() + 300
                return entries
            except Exception:
                self.failed = True
                self.expires = time.monotonic() + 30
                self.items = {}
                raise HTTPException(503, 'Galería temporalmente no disponible') from None

    async def media(self, file_id, range_header):
        if not re.fullmatch(r'[\w-]+', file_id):
            raise HTTPException(404, 'Archivo no publicado')
        await self.listing()
        item = self.items.get(file_id)
        if item is None:
            raise HTTPException(404, 'Archivo no publicado')
        if range_header and not re.fullmatch(r'bytes=(\d+-\d*|-\d+)', range_header):
            raise HTTPException(416, 'Rango no válido')
        try:
            await asyncio.wait_for(self.slots.acquire(), timeout=1)
        except TimeoutError:
            raise HTTPException(503, 'Galería ocupada') from None
        client = httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10))
        upstream = None
        closed = False
        async def cleanup():
            nonlocal closed
            if closed:
                return
            closed = True
            try:
                if upstream is not None:
                    await upstream.aclose()
                await client.aclose()
            finally:
                self.slots.release()
        try:
            headers = await self.get_headers()
            headers['Accept-Encoding'] = 'identity'
            if range_header:
                headers['Range'] = range_header
            req = client.build_request('GET', API + '/' + file_id, params={'alt': 'media'}, headers=headers)
            upstream = await client.send(req, stream=True)
            if upstream.status_code == 416:
                raise HTTPException(416, 'Rango no válido')
            if upstream.status_code not in (200, 206):
                raise HTTPException(503, 'No se pudo cargar el archivo')
            if upstream.headers.get('content-type', '').split(';')[0] != item['mime']:
                raise HTTPException(503, 'Formato de archivo modificado')
            limit = MAX_VIDEO if item['kind'] == 'video' else MAX_IMAGE
            if int(upstream.headers.get('content-length', 0)) > limit:
                raise HTTPException(413, 'Archivo demasiado grande')
            response_headers = {'Cache-Control': 'public, max-age=300', 'X-Content-Type-Options': 'nosniff',
                                'Accept-Ranges': 'bytes'}
            for name in ('content-length', 'content-range'):
                if name in upstream.headers:
                    response_headers[name] = upstream.headers[name]
            async def chunks():
                total = 0
                try:
                    async for chunk in upstream.aiter_bytes(65536):
                        total += len(chunk)
                        if total > limit:
                            raise RuntimeError('Media size limit')
                        yield chunk
                finally:
                    await cleanup()
            return StreamingResponse(chunks(), status_code=upstream.status_code,
                                     media_type=item['mime'], headers=response_headers,
                                     background=BackgroundTask(cleanup))
        except BaseException as exc:
            await cleanup()
            if isinstance(exc, (HTTPException, asyncio.CancelledError)):
                raise
            raise HTTPException(503, 'No se pudo cargar el archivo') from None
