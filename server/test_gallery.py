import os
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from fastapi import HTTPException
from gallery import Gallery, media_entry, MAX_VIDEO

RealClient = httpx.AsyncClient

def item(id='clip', mime='video/mp4', size=10):
    return {'id': id, 'mimeType': mime, 'size': str(size), 'capabilities': {'canDownload': True}}

class GalleryTests(unittest.IsolatedAsyncioTestCase):
    def test_formats_and_limits(self):
        self.assertIsNotNone(media_entry(item(), 'general'))
        for data in [item(mime='text/plain'), item(mime='image/svg+xml'), item(size=MAX_VIDEO+1), item(id='../secret')]:
            self.assertIsNone(media_entry(data, 'general'))
        data = item(); data['capabilities']['canDownload'] = False
        self.assertIsNone(media_entry(data, 'general'))

    async def test_listing_scope_pagination_and_cache(self):
        requested = []
        def handler(req):
            q = req.url.params['q']; requested.append(q)
            if "'root'" in q:
                return httpx.Response(200, json={'files': [item('rootclip'), {'id': 'region', 'name': 'Puna', 'mimeType': 'application/vnd.google-apps.folder'}, {'id': 'private', 'name': 'Privado', 'mimeType': 'application/vnd.google-apps.folder'}]})
            self.assertIn("'region'", q)
            if 'pageToken' in req.url.params:
                return httpx.Response(200, json={'files': [item('picture', 'image/jpeg')]})
            return httpx.Response(200, json={'nextPageToken': 'next', 'files': [item('doc', 'text/plain')]})
        with patch.dict(os.environ, {'DRIVE_MEDIA_FOLDER_ID': 'root'}), patch('gallery.httpx.AsyncClient', side_effect=lambda **kw: RealClient(transport=httpx.MockTransport(handler), **kw)):
            g = Gallery(AsyncMock(return_value={'Authorization': 'Bearer test'}))
            files = await g.listing()
            self.assertEqual([(i['id'], i['region']) for i in files], [('rootclip', 'general'), ('picture', 'puna')])
            await g.listing()
            self.assertEqual(len(requested), 3)

    async def test_unpublished_ids_and_invalid_range(self):
        g = Gallery(AsyncMock()); g.listing = AsyncMock(return_value=[])
        for file_id in ('secret-document', '../file'):
            with self.assertRaises(HTTPException) as e:
                await g.media(file_id, None)
            self.assertEqual(e.exception.status_code, 404)
        g.items['clip'] = media_entry(item(), 'general')
        with self.assertRaises(HTTPException) as e:
            await g.media('clip', 'bytes=0-1,3-4')
        self.assertEqual(e.exception.status_code, 416)

    async def test_partial_video_response_and_cleanup(self):
        def handler(req):
            self.assertEqual(req.headers['range'], 'bytes=2-5')
            self.assertEqual(req.url.params['alt'], 'media')
            return httpx.Response(206, content=b'2345', headers={'Content-Type': 'video/mp4', 'Content-Range': 'bytes 2-5/10'})
        g = Gallery(AsyncMock(return_value={'Authorization': 'Bearer test'}))
        g.listing = AsyncMock(return_value=[])
        g.items['clip'] = media_entry(item(), 'general')
        with patch('gallery.httpx.AsyncClient', side_effect=lambda **kw: RealClient(transport=httpx.MockTransport(handler), **kw)):
            response = await g.media('clip', 'bytes=2-5')
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.headers['content-range'], 'bytes 2-5/10')
            body = b''.join([chunk async for chunk in response.body_iterator])
            self.assertEqual(body, b'2345')
            await response.background()
            self.assertEqual(g.slots._value, 6)

    async def test_drive_failure_is_sanitized_and_cached(self):
        creds = AsyncMock(side_effect=RuntimeError('secret token'))
        g = Gallery(creds)
        with patch.dict(os.environ, {'DRIVE_MEDIA_FOLDER_ID': 'root'}):
            for _ in range(2):
                with self.assertRaises(HTTPException) as e:
                    await g.listing()
                self.assertEqual(e.exception.status_code, 503)
                self.assertNotIn('secret', e.exception.detail)
            self.assertEqual(creds.await_count, 1)

if __name__ == '__main__':
    unittest.main()
