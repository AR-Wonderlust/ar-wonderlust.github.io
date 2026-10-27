# Fotos y videos desde Drive

Carpeta seleccionada: https://drive.google.com/drive/folders/1apG5IsXUjhmB4Tabh126bA5qKlpitRu6

Compartir esta carpeta como Lector con `roma-asistente-drive@gen-lang-client-0905621291.iam.gserviceaccount.com` (si ya hereda ese acceso de la carpeta principal no hace falta repetirlo). No se necesita hacer pública la carpeta en Drive. Los archivos admitidos de esta carpeta se publican a través del servidor ROMA: subir solo material destinado a la web.

Se leen archivos directamente en Fotos web (categoría general) y en las subcarpetas Quebrada, Puna, Yungas, Valles. No se siguen accesos directos ni carpetas adicionales o anidadas. Los nombres de región no distinguen mayúsculas. Hasta 200 fotos/videos admitidos. La lista se actualiza al siguiente acceso una vez vencidos 5 minutos de caché; recargar la web para obtener la nueva selección. Tras borrar archivos puede haber hasta 5 minutos adicionales de caché del navegador.

Admitidos: MP4 H.264 (recomendado, 1080x1920 vertical, 8–15 segundos), JPG, PNG y WebP. No hay conversión automática de formatos. Límite de videos 25 MiB y fotos 5 MiB; conviene comprimir a 5–10 MB y menos de 1 MB respectivamente. Los archivos que exceden el límite no se publican.

## Aplicar en Ubuntu

```bash
cd ~/roma-asistente-web
git pull --ff-only
cd server
nano .env
```

Agregar una única línea (o actualizarla si ya existe):

```dotenv
DRIVE_MEDIA_FOLDER_ID=1apG5IsXUjhmB4Tabh126bA5qKlpitRu6
```

Conservar DRIVE_FOLDER_ID: sigue siendo la carpeta de documentos del chatbot. No cambiar las claves ni el modelo.

```bash
sudo docker compose config --quiet && sudo docker compose up -d --build assistant
curl --fail-with-body --max-time 120 http://127.0.0.1:8010/gallery -H 'Origin: https://ar-wonderlust.github.io'
```

La respuesta debe tener `items` con los archivos publicados. Si la lista está vacía, revisar formatos, tamaños y ubicación. Si devuelve 503, revisar acceso de la cuenta de servicio a la carpeta. No compartir .env ni credenciales en capturas.

## Presentación

Nueva sección bajo los servicios: hasta tres archivos distintos simultáneos en una superficie 16:9; en pantallas de hasta 700 px, uno en una superficie vertical. Se conserva la imagen completa sin recortes. Si hay uno o dos archivos, se muestran solo esos. Selección aleatoria cada 18 segundos y mediante Ver otros paisajes; puede repetirse un archivo entre selecciones sucesivas. Los filtros eligen región; archivos de la raíz aparecen en Todos.

Videos sin sonido, en bucle, con reproducción en línea. Pausa manual; pausa fuera de pantalla y con pestaña oculta. Con preferencia de movimiento reducido o ahorro de datos, se inicia pausado. Si el navegador bloquea la reproducción automática, tocar Reproducir. El chat y las fotos de fondo originales siguen disponibles si la galería falla o aún no se instaló el servidor.

## Funcionamiento y límites

Las credenciales quedan en el servidor. /media solo entrega IDs presentes en la lista permitida y formatos admitidos; no acepta URLs externas ni IDs arbitrarios de documentos. Se soportan solicitudes Range para MP4 mediante Drive API. Hay un máximo de seis transferencias simultáneas por proceso; el tráfico pasa por la VM y Cloudflare Tunnel, por lo que consume su conexión. Esta versión no copia todo Drive ni mantiene videos completos en RAM. Para tráfico alto convendrá almacenamiento/CDN de medios. La cuenta conserva su permiso de solo lectura.

Referencia de descarga parcial: https://developers.google.com/workspace/drive/api/guides/manage-downloads
