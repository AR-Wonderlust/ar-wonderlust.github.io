# ROMA: primera etapa de base comercial

Esta entrega incorpora PostgreSQL, consultas con código único, categorías, seguimiento,
métricas, catálogo revisable, importador de Drive y cola de eventos para n8n.
No cambia automáticamente el catálogo que usa Gemini ni envía emails o WhatsApp.
El sitio público continúa en GitHub Pages. El panel se ejecuta en otra aplicación/puerto.

## Alcance real

- Consultas: registro opcional desde el chat, resumen, nombre/contacto opcionales, código CON,
  responsable, próxima acción, vencimiento, etapas y motivo de pérdida.
- Un resumen guardado es una captura de ese momento. Mensajes posteriores no lo actualizan;
  se incluyen al enviar WhatsApp. No se deduce identidad ni se enlazan personas automáticamente.
- Métricas de consultas por mes/canal/categoría, etapas y seguimientos vencidos.
  Todas las capturas públicas son canal web; no existe todavía integración de WhatsApp entrante.
- Catálogo: borradores, revisión humana, fechas con año, permanentes, aprobación y archivo.
- PostgreSQL no confirma cupos ni genera reservas en esta etapa. “Aceptada” es una etapa comercial.
- Pendientes para siguientes entregas: clientes deduplicados, presupuestos versionados, ventas,
  cobros, costos, recursos, cupos/bloqueos transaccionales, sincronización Google Calendar,
  portal B2B, roles por operador y campañas con consentimiento independiente.

## Instalación en la VM

No hay acceso SSH directo desde ChatGPT: estos comandos se ejecutan en Ubuntu.
No se reemplazan los Postgres de n8n u otros sistemas. Se crea un volumen independiente.

```bash
cd ~/roma-asistente-web
git pull --ff-only
cd server
python3 setup_crm.py
nano .env.crm
```

El script genera contraseñas aleatorias, no las imprime ni sobrescribe un archivo existente.
Anotá localmente CRM_ADMIN_USER y CRM_ADMIN_PASSWORD. No compartas .env.crm.
Conservá CRM_BIND_IP=127.0.0.1 y CATALOG_SOURCE=drive para empezar.
PGPASSWORD protege el volumen: cambiar el archivo después de crear PostgreSQL no cambia
la contraseña del rol en la base. No lo regeneres ni borres el volumen.

```bash
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml config --quiet
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml up -d --build
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml ps
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml exec -T assistant python -m crm.smoke
```

Si config --quiet falla, detenerse y corregir antes de ejecutar up. La migración es
transaccional y versionada: si falla, los servicios nuevos no arrancan. Guardar una copia
externa del servidor antes de esta instalación y prever una breve recreación del asistente.
El PostgreSQL de este stack no publica el puerto 5432 en el host.
No ejecutar docker compose down -v: elimina la base.

En futuras actualizaciones usar SIEMPRE ambos archivos Compose y --env-file .env.crm.
No usar únicamente compose.yaml: no habilita el CRM en el asistente.

## Abrir el panel desde tu computadora por VPN + SSH

En la computadora personal (no dentro del servidor):

```bash
ssh -N -L 8011:127.0.0.1:8011 shifuleinad@172.27.91.193
```

Mantener esa terminal abierta y visitar http://127.0.0.1:8011.
Ingresar con las credenciales de .env.crm. La conexión al servidor viaja cifrada por SSH.
Si 8011 está ocupado localmente, usar 18011:127.0.0.1:8011 y abrir localhost:18011.
No agregar una ruta de Cloudflare Tunnel para el panel.

Alternativa VPN directa: configurar CRM_BIND_IP=172.27.91.193 solo si esa IP sigue
asignada a la VM y el acceso está restringido a los miembros autorizados de la VPN.
No usar 0.0.0.0. La autenticación inicial es una cuenta de operador compartida;
el registro de auditoría no distingue personas que usan esa misma cuenta.

## Probar desde la página

1. Recargar la web. Abrir el asistente e iniciar una consulta de prueba.
2. Abrir “Guardar mi consulta para seguimiento”. Completar un contacto de prueba si se desea.
3. Aceptar el guardado y pulsar Guardar. Debe aparecer CON-00000001 (o el siguiente).
4. Comprobar el registro en el panel. Un reintento de la misma captura no duplica la consulta.
5. Clasificar categorías, responsable y próxima acción; guardar.
6. Verificar que el enlace de WhatsApp contiene el código y el número 5493885383215.
   No es necesario enviar el mensaje para probar el enlace.

La base no almacena automáticamente cada turno. El consentimiento es de seguimiento,
no de marketing. Aplicar una política de retención y atender solicitudes de eliminación
antes de escalar captación; esta entrega no incorpora campañas ni exportación masiva.

## Drive: originales a borradores

Crear una carpeta Material Original y compartirla como lector con la cuenta de servicio
ya usada por el asistente. Puede contener subcarpetas año/mes. Configurar en .env.crm:

```dotenv
CRM_DRIVE_ORIGINAL_ID=ID_DE_MATERIAL_ORIGINAL
CRM_EXTRACTION_MODEL=MODELO_MULTIMODAL_DISPONIBLE_EN_TU_PROYECTO
```

El modelo se usa solo para PDF/JPEG/PNG/WebP. Utiliza GEMINI_API_KEY del .env existente;
verificar compatibilidad en el proyecto antes de programar la extracción. Puede generar cargos.
Docs/TXT/Markdown/CSV se leen sin IA. Docs se exporta a texto: para flyers insertados
en Docs subir el PDF exportado, porque la exportación de texto no contiene esas imágenes.
Videos se omiten con aviso en esta etapa. No se extrae por defecto la carpeta Fotos web.

Primera ejecución manual:

```bash
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml run --rm --no-deps crm-drive python -m crm.drive_import
```

Revisar la salida y las fichas pendientes en el panel. Procesa hasta 20 archivos nuevos
por pasada, hasta 8 MB por archivo; no trunca silenciosamente documentos largos.
La versión de Drive evita reprocesar material sin cambios. Un original modificado crea
un borrador nuevo; no reemplaza la ficha aprobada hasta que se apruebe la revisión.
Una eliminación en Drive NO elimina automáticamente una ficha aprobada: archivarla en el panel.
El importador escribe únicamente PostgreSQL; no crea carpetas ni modifica originales en Drive.
Pendiente y Aprobado pasan a ser estados del panel, evitando dos fuentes de aprobación.
Si un documento contiene varias actividades, crear fichas separadas antes de aprobarlo.
No deducir el año por el nombre de la carpeta. Revisar fechas, moneda, precio por persona/grupo,
prestador, contactos e inclusiones. Un error en la extracción no altera el catálogo aprobado.

Cuando la primera pasada sea satisfactoria, activar revisión cada 15 minutos:

```bash
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml --profile drive-import up -d crm-drive
```

Detenerla sin perder datos: el mismo comando base seguido de stop crm-drive.
Los errores de archivos se reintentan en la siguiente pasada; revisar logs ante fallos repetidos
para no repetir llamadas facturables innecesariamente.

## Usar el catálogo aprobado en Gemini

Primero aprobar al menos una ficha permanente o con fecha vigente. Después editar .env.crm:

```dotenv
CATALOG_SOURCE=postgres
```

Recrear assistant con los dos archivos Compose. El asistente recibirá solo fichas aprobadas
permanentes o no finalizadas, con la fecha actual de Jujuy. No consulta disponibilidad real
ni crea reservas. Esta versión envía hasta 50 fichas y mantiene el límite de 120000 caracteres;
la recuperación por fechas específicas/intereses se añadirá junto al módulo de salidas.
Para volver al comportamiento anterior, CATALOG_SOURCE=drive y recrear assistant.
El script check_assistant.py existente sigue diagnosticando Drive: para PostgreSQL usar
crm.smoke y una consulta real POST /chat.

## n8n: integración privada, sin mensajes automáticos

Importar server/n8n/roma-crm-events.json. El flujo queda DESACTIVADO.
Crear una credencial Header Auth en n8n:

- Name: Authorization
- Value: Bearer seguido de CRM_AUTOMATION_TOKEN (secreto de .env.crm).

Asignarla a los dos nodos HTTP. No insertar el token en el JSON del workflow.
Si n8n está en otro stack Docker, conectar solo su contenedor a la red del CRM:

```bash
sudo docker network connect roma-assistant_default n8n-docker-n8n-1
```

Confirmar nombres con docker network ls y docker ps antes de ejecutar. Persistir esta
red externa en el Compose de n8n para que la conexión sobreviva a una recreación.
El ejemplo usa http://crm-admin:8000 por la red privada Docker; nunca publicar ese endpoint.

Ejecutar manualmente el workflow: reclama eventos por cinco minutos y confirma su procesamiento.
Es una prueba de conectividad, NO manda correos, WhatsApp ni crea reservas. Después de validar,
puede activarse el disparador cada cinco minutos. Añadir acciones comerciales autorizadas
ANTES del nodo de confirmación. Si una acción falla, no confirmar: el evento será reintentado.
Guardar el event.id como clave de deduplicación en cualquier destino. La entrega es al menos
una vez; una acción que tuvo éxito antes de un fallo puede volver a ejecutarse.
La cola entrega tipo e ID interno; no expone conversaciones ni datos de contacto a n8n.

## Backups, recuperación y límites operativos

```bash
cd ~/roma-asistente-web/server
sudo bash backup_crm.sh
```

Copiar el dump a almacenamiento externo cifrado; el snapshot de la VM no sustituye esa copia.
Conservar .env.crm de forma segura. Probar la restauración en una base separada antes de
considerar el sistema listo para datos comerciales irremplazables. Ejemplo, con un nombre
de prueba que no exista y el archivo de backup correcto:

```bash
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml exec -T crm-db sh -c 'createdb -U "$POSTGRES_USER" roma_restore_test'
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml exec -T crm-db sh -c 'pg_restore -U "$POSTGRES_USER" -d roma_restore_test --exit-on-error' < backups/ARCHIVO.dump
```

Nunca restaurar sobre producción sin un plan de recuperación. Para desactivar captura pública,
usar únicamente el despliegue base temporalmente o CRM_ENABLED=false en el entorno efectivo;
el chat y WhatsApp seguirán funcionando, aunque la sección de guardar consulta se ocultará.
Hay un límite global de 20 capturas por minuto por proceso. No sustituye un control antiabuso
en Cloudflare si aparece spam. El MVP usa un único operador y un rol de base propietario;
antes de ampliar el equipo, separar roles, implementar sesiones individuales y retención.

## Verificaciones de desarrollo

```bash
python -m unittest discover -s tests -p 'test_crm*.py' -v
```

Las pruebas locales cubren validación, accesos privados, idempotencia del servicio con dobles,
errores sin datos sensibles y extracción a borradores. La prueba de esquema usa PGlite
(motor PostgreSQL embebido para QA), no reemplaza validar Docker/PostgreSQL en la VM.
