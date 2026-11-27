# RomAi · Voz web y WhatsApp

## Estado de esta etapa

La web conserva el chat escrito actual y agrega el botón flotante **Hablar con
RomAi**. El visitante mantiene presionado el botón, el navegador graba hasta
30 segundos y envía el audio al webhook de n8n. El navegador no contiene claves
de OpenAI, Supabase, Meta ni credenciales de n8n.

El botón de conversación en vivo queda visible como **próximamente**. Se activa
cuando `live_url` esté configurado, sin cambiar el resto de la página.

## Configuración Jekyll

Agregar los valores en la fuente privada de `site.data.roma`:

```yaml
voice:
  webhook_url: "https://N8N_PUBLICO/webhook/romai-web-voice"
  live_url: ""
```

`webhook_url` debe ser HTTPS y aceptar `multipart/form-data` con estos campos:

| Campo | Tipo | Uso |
|---|---|---|
| `audio` | archivo | Audio `webm/opus` u `ogg/opus` grabado por el navegador |
| `source` | texto | Siempre `web_ar_wonderlust` |
| `session_id` | texto | Identificador anónimo de la pestaña; no es un teléfono |

Respuesta esperada:

```json
{
  "transcript": "Quiero conocer Salinas Grandes",
  "reply": "Podemos revisar las opciones disponibles...",
  "audio_url": "https://.../respuesta.mp3"
}
```

También se acepta `audio_base64` junto con `audio_mime` en lugar de
`audio_url`. El frontend nunca interpreta instrucciones recibidas desde el
audio: n8n debe aplicar el mismo prompt, catálogo y validaciones del canal de
WhatsApp.

## Flujo recomendado en n8n

1. Webhook `romai-web-voice` recibe el archivo y limita tamaño, duración y
   frecuencia por `session_id`.
2. Transcripción con el mismo proveedor usado para WhatsApp.
3. Agente RomAi consulta `excursiones` y `documentos` en Supabase.
4. Si corresponde, pide nombre y teléfono antes de llamar a
   `romai-derivar`.
5. `romai-derivar` guarda `origen = web_ar_wonderlust` y hace upsert del
   cliente antes de pausar el bot.
6. TTS genera la respuesta y n8n devuelve el JSON anterior.

No colocar `X-RomAi-Key`, tokens ni claves de servicio en el JavaScript público.
La autenticación debe resolverse mediante un proxy del servidor ROMA o una URL
de webhook no reutilizable con límites y validación de origen.

## Segunda etapa: voz en vivo

Se puede conectar ElevenLabs, Vapi o Retell al mismo conjunto de herramientas
de n8n (`consultar_excursiones`, `buscar_info_general` y `derivar_a_roma`). El
widget debe llamar herramientas HTTPS protegidas y nunca consultar Supabase
directamente desde el navegador.
