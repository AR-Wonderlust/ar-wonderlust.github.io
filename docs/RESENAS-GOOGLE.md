# Reseñas de Google Maps

La sección «Jujuy, en primera persona» permite escribir una reseña y abrir la ficha de Google, incluso si el servidor falla. No publica comentarios ni puntajes de ejemplo.

Enlace de invitación: https://g.page/r/CeDpsUjiSiCXEAE/review
Place ID obtenido de la redirección de ese enlace: `ChIJD9EIu8kNG5QR4OmxSOJKIJc`.

## Activar las tarjetas automáticas

El backend ya ofrece GET /reviews. Se necesita habilitar Places API (New) en un proyecto de Google Cloud con facturación y una clave restringida a esa API; aplicar una restricción de IP solo si la IP de salida del servidor es estable. Configurar cuotas y alertas de presupuesto. La clave se conserva exclusivamente en server/.env, nunca en GitHub ni en el navegador. La credencial de Drive y la clave de Gemini no sustituyen esta configuración.

En la VM:

```bash
cd ~/roma-asistente-web
git pull --ff-only
cd server
nano .env
```

Agregar o actualizar (sin duplicar las variables):

```dotenv
GOOGLE_PLACES_API_KEY=TU_CLAVE_DE_PLACES
GOOGLE_PLACE_ID=ChIJD9EIu8kNG5QR4OmxSOJKIJc
```

Recrear y comprobar:

```bash
sudo docker compose config --quiet && sudo docker compose up -d --build assistant
curl --fail-with-body --max-time 20 http://127.0.0.1:8010/reviews -H 'Origin: https://ar-wonderlust.github.io'
```

Una respuesta con reviews vacío no confirma que Places esté configurado: el servidor también la devuelve cuando faltan clave o Place ID. Un 503 indica que la consulta a Google falló; revisar activación de API, facturación y restricciones. No compartir claves ni el archivo .env.

Google Places devuelve como máximo cinco reseñas por relevancia, no el historial completo ni necesariamente las últimas. Se muestran autor, atribución, enlaces y puntuación real. La web conserva la invitación si la API falla. El endpoint consulta Google bajo demanda, no sincroniza ni almacena reseñas en un archivo y no implementa una caché diaria. Cada visita puede generar una consulta facturable; revisar cuotas antes de habilitarla.

Referencias:
- https://developers.google.com/maps/documentation/places/web-service/place-details
- https://developers.google.com/maps/documentation/places/web-service/policies
