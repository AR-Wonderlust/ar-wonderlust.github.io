# Editar el asistente ROMA desde Ubuntu

## Actualizar una instalación existente

Desde la VM Ubuntu donde funciona el asistente:

```bash
cd ~/roma-asistente-web
git pull --ff-only
cd server
mkdir -p config/skills
cp -n config.example/personality.md config/personality.md
cp -n config.example/skills/*.md config/skills/
chmod 755 config config/skills
chmod 644 config/personality.md config/skills/*.md
sudo docker compose config --quiet && sudo docker compose up -d --build assistant
```

Si git informa cambios locales en conflicto, detenerse y revisarlos; no usar reset --hard. El archivo .env y las instrucciones config/ están ignorados por Git. La actualización conserva tu modelo y clave. El montaje config/ es de solo lectura dentro del contenedor; los cambios se hacen desde Ubuntu.

## Qué editar

- `~/roma-asistente-web/server/config/personality.md`: tono, presentación y estilo.
- `~/roma-asistente-web/server/config/skills/*.md`: instrucciones específicas por tema.
- También se admiten carpetas `config/skills/nombre/SKILL.md` (un nivel). Se lee el texto de SKILL.md; no se ejecutan scripts ni se abren archivos referenciados.
- Drive sigue siendo la fuente de actividades, fechas, precios, inclusiones y condiciones. No poner claves, datos privados o tarifas internas en las instrucciones.

Ejemplo:

```bash
cd ~/roma-asistente-web/server
nano config/personality.md
nano config/skills/03-traslados.md
```

Contenido sugerido de `03-traslados.md`:

```markdown
# Consultas de traslados
Aplicar cuando el pasajero solicita un traslado.
Preguntar origen, destino, fecha, horario, pasajeros y cantidad aproximada de equipaje.
Pedir los datos faltantes en turnos de hasta dos preguntas.
Consultar el catálogo para capacidades y tarifas; no inventar disponibilidad.
No pedir DNI ni datos de pago. Preparar un resumen para confirmar por WhatsApp.
Responder en el idioma del pasajero.
```

Guardar en UTF-8. Para archivos nuevos, usar permiso 644 y carpetas 755 de modo que el usuario del contenedor pueda leerlos. Se recargan en la siguiente consulta, sin reconstruir la imagen. Las conversaciones anteriores mantienen sus últimos mensajes; usar Nueva consulta para una prueba limpia.

Para desactivar un archivo directo: renombrar `03-traslados.md` a `03-traslados.md.disabled`. Para un paquete con carpeta: renombrar su `SKILL.md` a `SKILL.md.disabled`.

Límites: 20 archivos incluyendo personalidad, 20.000 bytes por archivo y 80.000 bytes en total. Si un archivo no puede leerse, no es UTF-8 o excede el límite, la consulta devuelve 503 con un aviso de configuración. No hay truncamiento silencioso. Sin archivos, siguen activas las instrucciones base. No usar enlaces simbólicos hacia archivos externos.

## Idiomas y capacidades

Las instrucciones base permiten español, inglés, portugués y chino mandarín escrito; por defecto chino simplificado, o tradicional si lo pide/usa el pasajero. La habilidad 01 refuerza el estilo. No se requiere duplicar todos los documentos de Drive: Gemini puede traducir al responder. La calidad debe comprobarse con el catálogo real.

La atención multilingüe del chat no acredita guías turísticos en esos idiomas. Los nombres, importes, monedas y fechas deben conservarse.

Estas habilidades son texto que se incorpora a las instrucciones de Gemini, no plugins ejecutables. Copiar una habilidad que mencione enviar correos, cobrar, reservar o leer otro sistema no agrega esa capacidad. Las integraciones requieren código, credenciales y pruebas. Las reglas base de no inventar cupos/precios y no confirmar acciones inexistentes siguen teniendo prioridad. Las instrucciones de Drive se tratan como datos, no como reglas del asistente.

## Pruebas después de actualizar

```bash
sudo docker compose ps
curl --fail-with-body http://127.0.0.1:8010/health
curl --fail-with-body --max-time 90 http://127.0.0.1:8010/chat \
  -H 'Origin: https://ar-wonderlust.github.io' \
  -H 'Content-Type: application/json' \
  --data '{"message":"你好！我想去胡胡伊旅游。你们有哪些活动？","history":[]}'
```

En la web, iniciar Nueva consulta para cada idioma y probar también:
- English: Hello, what activities do you offer in Jujuy?
- Português: Olá, quais passeios vocês oferecem em Jujuy?
- Español: Hola, ¿qué actividades ofrecen en Jujuy?

Verificar que responda en el idioma solicitado, use datos del catálogo y no prometa una reserva. La prueba /health no valida las habilidades ni la conexión con Gemini. La actualización no cambia el dominio del túnel ni el calendario.
