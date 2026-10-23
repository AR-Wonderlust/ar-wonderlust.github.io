# Instalar el asistente ROMA en Ubuntu / Proxmox

Ejecutar dentro de la VM Ubuntu, no en el host Proxmox. Se necesita Docker Engine y el plugin Docker Compose. El servicio usa 127.0.0.1:8010 para convivir con otras aplicaciones; Nginx debe correr en esa misma VM. No se activa el chat de la web hasta completar una prueba real.

## 1. Revisar el servidor

```bash
lsb_release -ds
docker --version
docker compose version
sudo docker ps --format 'table {{.Names}}\t{{.Ports}}'
sudo ss -ltnp | grep -E ':(80|443|8010)\b' || true
sudo nginx -t
```

Si Docker/Compose no están instalados, seguir https://docs.docker.com/engine/install/ubuntu/ según la versión de Ubuntu. No instalar paquetes alternativos encima de una instalación existente. Si Nginx falla por certificados previos, corregir esa configuración antes de agregar este servicio.

## 2. Descargar en una carpeta nueva

```bash
git clone https://github.com/AR-Wonderlust/ar-wonderlust.github.io.git ~/roma-asistente-web
cd ~/roma-asistente-web/server
(umask 077; cp -n .env.example .env)
nano .env
```

Completar GEMINI_API_KEY y GEMINI_MODEL con una clave y un modelo disponible en Google AI Studio (https://aistudio.google.com/apikey). Mantener DRIVE_FOLDER_ID y ALLOWED_ORIGIN ya definidos. Mantener Places vacío si no se van a configurar reseñas. No pegar claves en mensajes ni subir .env a Git. Para comprobar la sintaxis sin imprimir variables: `sudo docker compose config --quiet`.

## 3. Dar acceso de lectura a Drive

En Google Cloud, elegir el proyecto, habilitar Google Drive API y crear una cuenta de servicio para el asistente. Para leer esta carpeta compartida no necesita rol de Editor del proyecto ni delegación de dominio. Copiar su correo y compartir la carpeta siguiente con ese correo como Lector:

https://drive.google.com/drive/folders/1bx8lThxvYhkdb_ZCeUtnZOZSMMn6aZX6

Crear una clave JSON de esa cuenta y transferirla a la VM por un canal privado. No enviarla por chat. Guardarla así, sustituyendo la ruta del archivo descargado:

```bash
sudo install -d -m 0700 /etc/roma-assistant
sudo install -o 10001 -g 10001 -m 0400 /ruta/al/archivo-descargado.json /etc/roma-assistant/google-service-account.json
```

El usuario del contenedor tiene UID 10001. La carpeta del host queda accesible solo para root; el archivo se monta en modo lectura. Agregar al menos un Google Doc con información aprobada para pasajeros directamente en la carpeta. Se admiten además TXT, Markdown y CSV; no PDF, imágenes, Google Sheets ni subcarpetas.

## 4. Iniciar y probar

Desde `~/roma-asistente-web/server`:

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
curl --fail-with-body http://127.0.0.1:8010/health
curl --fail-with-body http://127.0.0.1:8010/chat \
  -H 'Origin: https://ar-wonderlust.github.io' \
  -H 'Content-Type: application/json' \
  --data '{"message":"¿Qué actividades ofrecen según el catálogo?","history":[]}'
```

/health comprueba el proceso; solo una respuesta real de /chat verifica Drive y Gemini. Un 503 puede indicar clave/modelo inválido, Drive API deshabilitada, permisos faltantes o carpeta vacía. Revisar localmente `sudo docker compose logs --tail=60 assistant`; no compartir credenciales. La caché se renueva bajo demanda después de cinco minutos.

## 5. Dominio y HTTPS

Propuesta de nombre (pendiente de confirmar): asistente.somosromaturismo.com. Crear su DNS hacia la IP pública del servidor y asegurar acceso de Internet a los puertos 80 y 443 del proxy. Si hay CGNAT o el proxy está en otra VM, adaptar esta parte antes de continuar. No exponer el puerto 8010 a Internet.

Crear un sitio Nginx independiente usando `docs/nginx-roma-http.conf.example`. Sustituir el dominio si corresponde. No reemplazar el sitio de n8n ni la configuración global. El archivo debe incluirse dentro del contexto http (como ocurre con sites-enabled en Ubuntu).

```bash
sudo cp ../docs/nginx-roma-http.conf.example /etc/nginx/sites-available/roma-assistant
sudo ln -s /etc/nginx/sites-available/roma-assistant /etc/nginx/sites-enabled/roma-assistant
sudo nginx -t
```

Solo si la comprobación termina correctamente:

```bash
sudo systemctl reload nginx
```

Obtener el certificado con Certbot y su plugin Nginx ya instalado, cuando DNS y puertos estén verificados:

```bash
sudo certbot --nginx -d asistente.somosromaturismo.com --redirect
```

Comprobar desde otra conexión /health y /chat por HTTPS. El endpoint público requiere el encabezado Origin en /chat. Los límites de Nginx y de la aplicación reducen consumo, pero no sustituyen controles de presupuesto en Google.

## 6. Conectar la página

Tras validar una respuesta real por HTTPS, configurar `_data/roma.yml` con `api_url: "https://asistente.somosromaturismo.com"` (o el dominio elegido). Publicar y comprobar desde la página. No poner claves en ese archivo. Si falla, volver `api_url` a vacío para recuperar la demostración guiada.

Para detener solo este servicio: `sudo docker compose stop`. Para actualizar: revisar los cambios, hacer `git pull --ff-only` y `sudo docker compose up -d --build` desde server. Los archivos privados permanecen fuera de Git.

Referencias: https://docs.docker.com/engine/install/ubuntu/ ; https://ai.google.dev/gemini-api/docs/api-key ; https://developers.google.com/workspace/drive/api/guides/manage-downloads
