# TRANSPORTE-ROMA-2026: lectura inicial de tarifas

Workflow: `server/n8n/roma-transporte-tarifas-preview.json`.
Es una prueba manual de lectura y validación; no conecta WhatsApp Cloud, no guarda presupuestos en CRM y no envía mensajes. No requiere reconstruir contenedores.

## Instalar en n8n

1. Importar el archivo JSON como workflow nuevo. No reemplazar el piloto de grupos.
2. En **Leer tarifas de Google Sheets**, elegir una credencial Google Sheets OAuth2 existente o configurarla con una cuenta que pueda leer el documento. Habilitar Google Sheets API en el proyecto si falta. Las credenciales se guardan en n8n, nunca en GitHub.
3. Ejecutar **Prueba manual** y revisar la salida de **Validar niveles comerciales**.

Se consulta exclusivamente `'TRANSPORTE-ROMA-2026'!D1:L3` mediante Sheets API con `UNFORMATTED_VALUE`: lee valores numéricos calculados y no importa filas de clientes ni otras pestañas. La salida queda en la ejecución de prueba. Cualquier encabezado distinto, tarifa vacía/no numérica/no positiva u orden verde >= amarillo >= rojo inválido detiene el flujo.

## Reglas confirmadas por Daniel

- Amarillo: tarifa habitual de venta.
- Rojo: piso de descuento para varios viajes, sujeto a aprobación humana; no se aplica automáticamente.
- Verde: referencia disponible; falta definir cuándo ofrecerla.
- Colores: niveles comerciales, no temporadas. Se conserva el documento sin modificarlo.
- Las tarifas por km incluyen chofer y combustible, por vehículo completo.
- Km facturables: ida, regreso y movimientos operativos sin pasajeros.
- Auto: traslado con chofer. Los alquileres se gestionan en otra ficha.

Mapeo confirmado el 3/11/2026: excursión D/E/F, traslado G/H/I, auto J/K/L, fila 3. No incluye las columnas SALIO ni ALTA/MEDIA/BAJA.

El código del nodo está disponible en `server/n8n/validar-transporte.js`. Requiere la respuesta completa de Sheets, con `range` y `values`, y devuelve únicamente `source` y `rates` para el CRM. En Guardar tarifas en CRM usar JSON en modo Expression: `{{ $json }}`.

Para importar al CRM y preparar presupuestos, seguir `docs/TRANSPORTE-PRESUPUESTOS.md`. El servidor debe estar actualizado para aceptar D1:L3; los presupuestos existentes conservan sus tarifas históricas.
