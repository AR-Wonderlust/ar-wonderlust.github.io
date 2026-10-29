"""Run inside the assistant container. Never prints credentials or document contents."""
import asyncio
import os
import re
import sys
import google.auth
import httpx
import app
from instructions import load_instructions

async def main():
    print('DIAGNÓSTICO ROMA (no modifica documentos ni envía WhatsApp)')
    try:
        text = load_instructions()
        print('INSTRUCCIONES: OK; caracteres:', len(text))
    except Exception as exc:
        print('INSTRUCCIONES: ERROR', type(exc).__name__)
        return 1
    try:
        app.credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/drive.readonly'])
        headers = await app.drive_headers()
        folder = os.getenv('DRIVE_FOLDER_ID', '')
        if not re.fullmatch(r'[\w-]+', folder):
            print('DRIVE: falta configurar DRIVE_FOLDER_ID')
            return 1
        files, token = [], None
        async with httpx.AsyncClient(timeout=20) as client:
            for _ in range(20):
                params = {'q': f"'{folder}' in parents and trashed=false", 'fields': 'nextPageToken,files(id,name,mimeType,size)', 'pageSize': 100}
                if token:
                    params['pageToken'] = token
                res = await client.get('https://www.googleapis.com/drive/v3/files', params=params, headers=headers)
                res.raise_for_status()
                data = res.json()
                files.extend(f for f in data.get('files', []) if f.get('mimeType') in ('application/vnd.google-apps.document', 'text/plain', 'text/markdown', 'text/csv'))
                token = data.get('nextPageToken')
                if not token:
                    break
            else:
                print('DRIVE: demasiados archivos para completar el diagnóstico')
                return 1
        print('DOCUMENTOS COMPATIBLES:', len(files), '(máximo 50)')
        if len(files) > 50:
            print('ACCIÓN: conservar hasta 50 documentos compatibles en la carpeta del catálogo.')
            return 1
        oversized = False
        async with httpx.AsyncClient(timeout=20) as client:
            for f in files:
                name = ''.join(c for c in f.get('name', '') if c.isprintable())[:120]
                try:
                    text = await app.read_catalog_document(client, f, headers)
                    print('TEXTO OK:', name, '| caracteres:', len(text),
                          '| tamaño del archivo en Drive:', f.get('size', 'no informado'))
                except app.HTTPException as exc:
                    if exc.detail != 'Texto de un documento demasiado grande; resumir su contenido.':
                        raise
                    oversized = True
                    print('TEXTO EXCESIVO:', name, '| supera 200000 bytes de texto descargado.')
        if oversized:
            print('ACCIÓN: resumir el texto de los documentos indicados. No hace falta eliminar imágenes de Google Docs.')
            return 1
        knowledge = await asyncio.wait_for(app.catalog(), timeout=90)
        print('CATÁLOGO: OK; caracteres:', len(knowledge), '(máximo 120000)')
    except httpx.HTTPStatusError as exc:
        print('DRIVE: HTTP', exc.response.status_code)
        return 1
    except Exception as exc:
        print('CATÁLOGO: ERROR', type(exc).__name__)
        detail = getattr(exc, 'detail', '')
        # Only known application messages, never upstream exception strings.
        if detail in ('Catálogo demasiado grande.', 'No hay actividades publicadas en la carpeta.', 'Texto de un documento demasiado grande; resumir su contenido.'):
            print(detail)
        return 1
    try:
        result = await asyncio.wait_for(app.chat(app.ChatRequest(message='Hola, ¿qué actividades ofrece ROMA según el catálogo?', history=[])), timeout=45)
        if not result.get('reply', '').strip():
            raise ValueError('Empty reply')
        print('CHAT INTEGRAL: OK; Gemini respondió usando la ruta real del asistente.')
        return 0
    except Exception as exc:
        print('CHAT INTEGRAL: ERROR', type(exc).__name__)
        key = os.getenv('GEMINI_API_KEY', '').strip()
        model = os.getenv('GEMINI_MODEL', '').strip()
        if not key or not re.fullmatch(r'[\w.-]+', model):
            print('GEMINI: revisar clave presente y nombre de modelo (sin models/).')
            return 1
        try:
            async with httpx.AsyncClient(timeout=35) as client:
                res = await client.post('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent', headers={'x-goog-api-key': key}, json={'contents': [{'parts': [{'text': 'Responde únicamente OK'}]}], 'generationConfig': {'maxOutputTokens': 100}})
                print('GEMINI AISLADO: HTTP', res.status_code)
                print('Referencia: 400 solicitud/modelo; 403 permisos; 404 modelo; 429 cuota; 503 disponibilidad temporal.')
        except Exception as exc:
            print('GEMINI AISLADO:', type(exc).__name__)
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
