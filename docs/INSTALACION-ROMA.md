# Agencia ROMA — actualización Jekyll

Integración preparada el 21/10/2026 sobre AR-Wonderlust/ar-wonderlust.github.io, commit base 7ec0a016936a266fdaa5ebec63b2d6368dd3b481. Rama de trabajo: feature/roma-portada-chat. Las integraciones de Google requieren configuración antes de activar el servicio.

## Qué contiene

- Portada adaptable a móvil, tablet y escritorio, inspirada en la referencia compartida.
- Selector de paisajes de Quebrada, Puna, Yungas y Valles. Fotografías reales con créditos.
- Chat en portada. Sin API configurada muestra explícitamente una demostración guiada; recoge respuestas para preparar un mensaje de WhatsApp. Con API configurada conversa mediante Gemini.
- Calendario mensual de muestra sin eventos ficticios; se reemplaza por Google Calendar al ingresar su ID. En celulares se abre inicialmente en formato agenda.
- Opiniones mediante Google Places API, con autor, enlace original y atribución. No se inventan testimonios.
- Servicio Python para leer la carpeta de actividades de Drive y responder con Gemini. El navegador nunca recibe claves privadas.

## Integración con el repositorio real

Estos archivos se prepararon sobre una copia del repositorio público, rama main. La actualización conserva las páginas, posts, imágenes y layouts existentes. La portada utiliza `_layouts/roma.html`; el listado anterior se mantiene en `/blog/` con el layout home y su paginación.

El paquete ZIP contiene solo los archivos nuevos o modificados. Aplicarlos en una rama, conservando el resto del repositorio. No borrar carpetas existentes ni subir el ZIP como si fuera una página. `preview.html` permite revisar el diseño y está excluido de la compilación.

Se agregó un Gemfile activo con Jekyll 3.10 y los plugins del sitio. La configuración conserva Minima, define la URL real, corrige colores y navegación y elimina la clave paginate duplicada. La carpeta server queda excluida de la web pública; no se agregaron credenciales.

Se agregó `.github/workflows/jekyll-check.yml`, que compila al abrir un pull request o ejecutarlo manualmente. No cambia la configuración de publicación de GitHub Pages. Antes de fusionar, verificar que esa comprobación pase. Este entorno no dispone de Ruby y la instalación fue impedida por permisos del sistema; la compilación Jekyll no se ejecutó aquí.

El logo existente `assets/img/logo-roma.png` pertenece a Casa ROMA. Se conserva; falta el archivo del logo Agencia ROMA para sustituir la marca tipográfica de la nueva portada. Los textos de ejemplo de páginas históricas tampoco se sobrescriben.

## Configuración pública

Editar `_data/roma.yml`:

- `api_url`: URL HTTPS del servicio, sin `/chat` final.
- `calendar_id`: ID del calendario público exclusivo de actividades. Google Calendar → Configuración del calendario → Integrar calendario. Habilitar visibilidad pública solo para ese calendario, sin datos de reservas o pasajeros. No es una carpeta de Drive.
- `whatsapp`: número con código de país, sin signos. Contacto de Agencia ROMA: `5493885383215` (+54 9 388 538-3215).
- `maps_url`: enlace a la ficha correcta de Agencia ROMA. El servidor puede devolverlo automáticamente.

La marca de la cabecera es tipográfica: falta el archivo original del logo para incorporarlo sin pérdida de calidad. No se recortó el logo de la fotografía del monitor.

## Carpeta de Drive

Crear una carpeta dedicada exclusivamente a información aprobada para pasajeros. Activar Google Drive API en Google Cloud, crear una cuenta de servicio y compartir solo esa carpeta con su correo, como lector. Guardar su credencial JSON exclusivamente en el servidor.

La versión inicial lee archivos directamente dentro de la carpeta: Google Docs, TXT, Markdown y CSV. No lee subcarpetas, PDF, imágenes ni Google Sheets. Convertirlos a Google Docs o TXT. Límite inicial: 50 documentos, 120.000 caracteres totales. Si se supera, devuelve error para evitar responder con un catálogo incompleto.

Usar una ficha por actividad: nombre, región, descripción, recorrido, punto de salida, horarios, días, duración, exigencia física, restricciones, idiomas, inclusiones, exclusiones, tarifa y moneda, vigencia, política de cancelación y contacto. Separar tarifas internas de la información pública; no subir datos de pasajeros.

La información se vuelve a leer en la siguiente consulta una vez vencidos 5 minutos de caché (`CATALOG_TTL`). No es entrenamiento del modelo ni sincronización instantánea. Las bajas y cambios se reflejan después de ese intervalo. Si la lectura falla, el bot no usa información vencida.

## Servidor de Gemini y Google Maps

1. Completar las variables de `server/.env.example` en un archivo privado `.env` fuera de Git. Elegir en Google AI Studio un modelo disponible y copiar su identificador en `GEMINI_MODEL`.
2. Activar Places API (New) si se desean reseñas automáticas. Configurar `GOOGLE_PLACES_API_KEY` y el `GOOGLE_PLACE_ID` de la ficha verificada. Esta API puede requerir facturación y devuelve una selección de reseñas, no todo el historial. No usar scraping.
3. Construir desde `server/`: `docker build -t roma-assistant .`
4. Ejecutar con variables de entorno y credencial montada como secreto. Ejemplo (sustituir rutas):

```bash
docker run -d --name roma-assistant --restart unless-stopped \
  --env-file /ruta/privada/roma.env \
  -v /ruta/privada/google-service-account.json:/run/secrets/google-service-account.json:ro \
  -p 127.0.0.1:8000:8000 roma-assistant
```

5. Configurar Nginx con HTTPS hacia `127.0.0.1:8000`, límites de tamaño y tráfico. Ver `docs/nginx.conf.example`. El origen debe coincidir exactamente con tu web, sin rutas ni barra final; para un proyecto GitHub Pages será `https://usuario.github.io`, aunque la página esté dentro de `/repositorio/`.
6. La API tiene límites globales por proceso, validación de mensajes y CORS; CORS no es autenticación. Mantener un solo worker para esos límites. Antes de exposición pública masiva, agregar protección antibots/cuotas en el proxy y alertas de presupuesto en Google Cloud. No publicar un endpoint sin límite de consumo.
7. Este servidor no ejecuta reservas ni confirma cupos. Gemini solo orienta con el catálogo. Las reservas se coordinan con el equipo.

## Privacidad y reseñas

Revisar el aviso de privacidad incluido para adecuarlo a la operación real y la política de datos del proyecto Gemini contratado. No activar registros de cuerpos de mensajes. No hay almacenamiento de conversaciones en esta implementación; se conservan en memoria de la pestaña hasta recargar o pulsar Nueva consulta. WhatsApp abre un borrador, nunca envía automáticamente.

Las reseñas conservan texto original, autor, foto y enlaces disponibles. Mantener la atribución visible de Google Maps. Para testimonios directos aún no incluidos, reunir texto autorizado, nombre de publicación y consentimiento; no agregarlos como si fueran reseñas de Google.

## Comprobación antes de publicar

- Compilar el repositorio completo con Jekyll y probar en móvil, tablet y escritorio.
- Revisar navegación, paisajes, contraste, teclado, Nueva consulta y borrador de WhatsApp.
- Probar preguntas sobre fechas, pasajeros y destinos; una pregunta sin respuesta en el catálogo debe derivar al equipo.
- Modificar una ficha de Drive y verificar después de 5 minutos. Eliminarla y volver a verificar.
- Confirmar que Calendar muestre los eventos públicos correctos y que Maps devuelva la ficha propia.
- Simular un error de Gemini o Drive: debe ofrecer continuar por WhatsApp y no inventar una respuesta.

## Documentación de referencia

- Gemini: https://ai.google.dev/api/generate-content
- Drive, descarga y exportación: https://developers.google.com/workspace/drive/api/guides/manage-downloads
- Google Places y atribuciones: https://developers.google.com/maps/documentation/places/web-service/policies

## Para completar la activación

Faltan: carpeta de Drive, ID de Calendar, enlace/Place ID de Google Maps, logo de Agencia ROMA y datos del servidor que alojará la API. Configurar secretos directamente en el servidor; no compartirlos en archivos públicos.
