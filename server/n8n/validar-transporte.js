// D1:L3: tres niveles por servicio. No incluye alquileres.
const input = $input.first().json;
let data = input.body ?? input;
if (typeof data === 'string') data = JSON.parse(data);
const rows = data.values;
if (!Array.isArray(rows) || !Array.isArray(rows[0]) || !Array.isArray(rows[2]))
  throw new Error('Se requiere la respuesta de Sheets con values para D1:L3');
if (!/^'?TRANSPORTE-ROMA-2026'?!D1:L3$/.test(data.range || ''))
  throw new Error('Rango incorrecto: volver a leer D1:L3');
const normalize = x => String(x ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toUpperCase();
const groups = [
  {service:'excursion', header:'EXCURSION', start:0},
  {service:'traslado', header:'TRASLADO', start:3},
  {service:'auto', header:'AUTO', start:6},
];
const rates = groups.map(g => {
  const prices = [0,1,2].map(offset => {
    const i = g.start + offset;
    const column = String.fromCharCode(68 + i);
    if (normalize(rows[0][i]) !== g.header)
      throw new Error('Encabezado incorrecto en ' + column + '1: se esperaba ' + g.header);
    const n = rows[2][i];
    if (typeof n !== 'number' || !Number.isFinite(n) || n <= 0 || n > 10000000)
      throw new Error('Tarifa inválida en ' + column + '3');
    return n;
  });
  const [green, yellow, red] = prices;
  if (!(green >= yellow && yellow >= red))
    throw new Error('Orden verde/amarillo/rojo inválido en ' + g.service);
  return {service:g.service, green_reference:green, yellow_standard:yellow, red_floor:red};
});
return [{json:{
  source:{spreadsheet_id:'1W55J03Uy1sY15Wj649_JDslyg1vCiBNHDpB5pvjTMS8',
    sheet:'TRANSPORTE-ROMA-2026', range:'D1:L3', read_at:new Date().toISOString()},
  rates
}}];
