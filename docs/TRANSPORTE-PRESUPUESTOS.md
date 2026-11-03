# Presupuestos de transporte

Implementa importación privada de tarifas, cálculo por tramos, borrador persistido y aprobación humana. No envía WhatsApp, no consulta calendarios y no reserva vehículos. No incorpora aún lectura de mensajes privados ni extracción IA del itinerario.

## Despliegue
Desde `~/roma-asistente-web`, ejecutar `git pull --ff-only`. Luego:

```bash
cd server
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml -f compose.whatsapp.yaml build crm-admin crm-migrate
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml -f compose.whatsapp.yaml run --rm crm-migrate
sudo docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml -f compose.whatsapp.yaml up -d --no-deps crm-admin
```

La migración 005 agrega dos tablas sin modificar las anteriores. Conservar los archivos .env y volúmenes. El rollback de la aplicación no requiere borrar estas tablas.

## n8n
Importar `server/n8n/roma-transporte-tarifas-crm.json` como workflow separado. Mantener el workflow de grupos existente.
1. Seleccionar la credencial Google conectada en el nodo de lectura (si es Google OAuth2 API genérica, cambiar el tipo predefinido a ese mismo tipo).
2. Seleccionar Header Auth en Guardar tarifas en CRM: nombre Authorization y valor Bearer seguido del CRM_AUTOMATION_TOKEN.
3. Ejecutar manualmente. La salida final debe contener rate_id, status importado, can_send false.

Si preferís conservar tus nodos actuales, agregar después de Validar niveles comerciales un HTTP Request POST a `http://crm-admin:8000/automation/transport/rates`, con esa credencial y cuerpo JSON en modo Expression:

```javascript
{{ JSON.stringify({source:$json.source,rates:$json.rates.map(r=>({service:r.service,green_reference:r.green_reference,yellow_standard:r.yellow_standard,red_floor:r.red_floor}))}) }}
```

Solo se importan D1:L3; no clientes. El servidor valida servicios, precios positivos, orden de niveles y lectura reciente (24 horas). Repetir exactamente una importación es idempotente. La fecha de lectura no confirma vigencia comercial; la revisa el operador.

## Panel
Abrir `http://172.27.91.193:8011/presupuestos` o el enlace Presupuestos de transporte en Gestión comercial. Seleccionar una consulta existente. Su resumen, pasajeros y fecha se muestran como referencia. Completar un tramo por vehículo, fecha, recorrido, pasajeros, capacidad habilitada y kilómetros operativos totales. No multiplicar por pasajeros ni duplicar los kilómetros de regreso ya incluidos.

La tarifa habitual es amarilla; combustible y chofer incluidos. Un descuento exige marcar varios viajes y explicar el motivo, nunca por debajo del rojo. Verde no habilitado. Alquileres y tarifa diaria fuera de este módulo.

Guardar calcula en Python con Decimal, redondea cada tramo a centavos, conserva la tarifa importada y registra auditoría. El doble envío del mismo formulario no duplica. Cambiar datos crea un nuevo borrador: los anteriores permanecen inmutables.

Aprobar exige kilómetros confirmados, capacidad suficiente, fechas no vencidas y las cuatro confirmaciones humanas: disponibilidad, capacidad/equipaje, vigencia comercial y adicionales. Aprobar NO bloquea disponibilidad. El operador debe comprobarla en su agenda antes de aprobar.

Luego aparece texto aprobado para copiar manualmente; no contiene el piso rojo ni niveles internos. En esta etapa no se envían mensajes ni se actualiza automáticamente el estado comercial de la consulta. La lista muestra los últimos 100 presupuestos y hasta 1000 consultas recientes en el selector.

## Prueba
Crear un traslado con 192 km y tarifa amarilla 1150: subtotal esperado 220800, independientemente de 4 o 12 pasajeros dentro de la capacidad. Probar un descuento debajo de 921: debe rechazarse. Un borrador con kilómetros estimados o pasajeros superiores a capacidad puede guardarse, pero no aprobarse. Confirmar una aprobación y verificar que no se envió WhatsApp.
