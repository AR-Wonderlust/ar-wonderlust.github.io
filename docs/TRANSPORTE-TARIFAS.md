# TRANSPORTE-ROMA-2026: lectura inicial de tarifas

Workflow: `server/n8n/roma-transporte-tarifas-preview.json`.
Es una prueba manual de lectura y validación; no conecta WhatsApp Cloud, no guarda presupuestos en CRM y no envía mensajes. No requiere reconstruir contenedores.

## Instalar en n8n

1. Importar el archivo JSON como workflow nuevo. No reemplazar el piloto de grupos.
2. En **Leer tarifas de Google Sheets**, elegir una credencial Google Sheets OAuth2 existente o configurarla con una cuenta que pueda leer el documento. Habilitar Google Sheets API en el proyecto si falta. Las credenciales se guardan en n8n, nunca en GitHub.
3. Ejecutar **Prueba manual** y revisar la salida de **Validar niveles comerciales**.

Se consulta exclusivamente `'TRANSPORTE-ROMA-2026'!E1:N3` mediante Sheets API con `UNFORMATTED_VALUE`: lee valores numéricos calculados y no importa filas de clientes ni otras pestañas. La salida queda en la ejecución de prueba. Cualquier encabezado distinto, tarifa vacía/no numérica/no positiva u orden verde >= amarillo >= rojo inválido detiene el flujo.

## Reglas confirmadas por Daniel

- Amarillo: tarifa habitual de venta.
- Rojo: piso de descuento para varios viajes, sujeto a aprobación humana; no se aplica automáticamente.
- Verde: referencia disponible; falta definir cuándo ofrecerla.
- Colores: niveles comerciales, no temporadas. Se conserva el documento sin modificarlo.
- Van: propuesta de ARS 250.000 por día con chofer, kilometraje libre, sin combustible para viajes de más de 400 km. Queda deshabilitada en el cálculo hasta aclarar si 400 km es por día o por viaje y la relación con columna D.

Mapeo explícito: excursión E/F/G, traslado H/I/J, auto K/M/N, fila 3. L (UBER XL) queda fuera porque L3 es texto. Los valores se leen en cada ejecución, no se fijan en el código.

## Diferencia detectada

En la exportación revisada el 2/11/2026, D3 dice `Dia - Sin Combustible`, pero D4 calcula `0.6*E4`. Por eso no se usa esa columna como tarifa diaria de 250.000 ni se modifica automáticamente. La anotación X2 recomienda alquiler de van para más de tres días: también debe armonizarse con el umbral de 400 km.

## Próxima etapa

Confirmar umbral y vigencia, km facturables (ida/retorno/reposicionamiento), inclusión de combustible en tarifas por km, viáticos/peajes/esperas de la modalidad diaria. Después integrar ficha multitramos, cálculo decimal determinista, disponibilidad, versión de presupuesto, aprobación humana y envío controlado. Cambiar datos o precio después de aprobar debe invalidar la aprobación. Un presupuesto no reserva capacidad por sí mismo.
