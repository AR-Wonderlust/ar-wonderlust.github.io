# Diagnóstico y respaldo del chat ROMA

La página comprueba la respuesta real de /chat en cada consulta. Si falla la red, vence el plazo de 35 segundos, la API devuelve error o no contiene respuesta, pasa a Consulta guiada. No se usa /health como prueba de Gemini, ni se consume una llamada de IA adicional por cada visitante.

El respaldo informa que la IA no está disponible y pregunta pasajeros, fechas, excursiones/servicios y origen/alojamiento. Conserva la consulta inicial, muestra un resumen y prepara el enlace al WhatsApp ya configurado. Funciona en el navegador sin depender de Drive, Gemini o la VM. No inventa precios ni disponibilidad. La conversación permanece en la pestaña y no se guarda en una base de datos.

El visitante debe pulsar Enviar al WhatsApp, revisar el mensaje y enviarlo desde WhatsApp. No hay envío automático ni confirmación falsa de recepción. Una integración de envío automático requeriría configurar la plataforma de WhatsApp Business o un flujo equivalente autorizado.

El respaldo continúa durante esa conversación aunque vuelva la IA, para no mezclar los pasos. Nueva consulta vuelve a intentar la IA. Admite textos guiados en español, inglés, portugués y chino; la detección local de idioma es aproximada. Cada respuesta guiada admite hasta 600 caracteres. El resumen incluye la consulta inicial (abreviada y marcada si era extensa), las cuatro respuestas y la última aclaración adicional; no extrae ni interpreta automáticamente fechas/cantidades de texto libre.

## Prueba interna en Ubuntu

Actualizar el repositorio y reconstruir para instalar el script; el respaldo de la página se publica independientemente y no necesita este paso.

```bash
cd ~/roma-asistente-web
git pull --ff-only
cd server
sudo docker compose config --quiet && sudo docker compose up -d --build assistant
sudo docker compose exec -T assistant python check_assistant.py
```

El script comprueba instrucciones, credenciales de Drive, cantidad/tamaño de documentos, catálogo completo y una respuesta real de Gemini a través de app.chat. Si la prueba integral falla, prueba Gemini aisladamente para informar el código HTTP. Consume una llamada de IA y, en caso de fallo, hasta una adicional. No imprime claves, contenido de documentos ni respuestas de pasajeros. Sí identifica el nombre de archivos excesivos para que el operador pueda corregirlos. No se ejecuta automáticamente ni envía mensajes.

El estado healthy de Docker solo indica que /health funciona; no acredita Gemini ni Drive.

## Error detectado: catálogo demasiado grande

Límites actuales del servidor: hasta 50 documentos compatibles; hasta 200000 bytes de texto descargado por documento (Google Docs se exporta a texto plano; su tamaño de almacenamiento no bloquea la lectura); hasta 120000 caracteres entre todos los documentos exportados. Los errores públicos distinguen exceso de documentos, exceso de texto por documento y exceso de caracteres del catálogo completo. Fotos y videos no cuentan como documentos compatibles. Se leen Docs, TXT, Markdown y CSV directamente en la carpeta del catálogo.

Si se supera el límite, usar documentos breves con actividades, vigencia, inclusiones y condiciones. Mover los originales extensos a otra carpeta conservándolos; no hace falta borrarlos. Dividir documentos sin reducir el total puede superar el límite de 50. Después de corregir Drive, iniciar Nueva consulta y repetir el diagnóstico. No aumentar límites indiscriminadamente: afecta latencia, contexto y consumo de Gemini.
