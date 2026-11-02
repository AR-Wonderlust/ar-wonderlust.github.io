'use strict';
const token=location.hash.slice(1),form=document.querySelector('#trip'),statusBox=document.querySelector('#status');
const categories={transfer:'Transfer aeroportuario',traslado:'Traslado',alojamiento_yala:'Alojamiento en Yala',alojamiento_carmen:'Alojamiento en El Carmen',alquiler_vehiculo:'Alquiler de vehículo',actividad:'Excursión / actividad',ticket:'Ticket',paquete:'Paquete',otro:'Consulta de viaje'};
let submissionId=null;
async function call(path,data){const r=await fetch(path,{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const b=await r.json();if(!r.ok)throw Error(typeof b.detail==='string'?b.detail:'Revisá los campos: nombre, pasajeros, teléfono, horario y fechas.');return b;}
function success(){form.hidden=true;document.querySelector('#success').hidden=false;statusBox.textContent='';}
async function init(){
 if(!/^[A-Za-z0-9_-]{43}$/.test(token)){statusBox.textContent='Falta el enlace completo. Abrí el enlace que te envió ROMA por WhatsApp.';return;}
 try{const d=await call('/solicitud/read',{token});if(d.submitted){success();return;}
  document.querySelector('#service').textContent=categories[d.fields.category]||'Consulta de viaje';
  document.querySelector('#expiry').textContent='Enlace disponible hasta '+new Date(d.expires_at).toLocaleDateString('es-AR',{timeZone:'America/Argentina/Jujuy'});
  for(const [k,v]of Object.entries(d.fields)){const input=form.elements.namedItem(k);if(input&&k!=='consent')input.value=v??'';}
  for(const item of document.querySelectorAll('[data-services]'))item.hidden=!item.dataset.services.split(' ').includes(d.fields.category);
  if(d.fields.extra_question){document.querySelector('#question-section').hidden=false;document.querySelector('#question').textContent=d.fields.extra_question;}
  statusBox.textContent='';form.hidden=false;
 }catch(e){statusBox.textContent=e.message;}
}
form.addEventListener('submit',async e=>{
 e.preventDefault();if(!form.reportValidity())return;
 const d=Object.fromEntries(new FormData(form));d.passengers=Number(d.passengers);d.travel_date=d.travel_date||null;d.end_date=d.end_date||null;d.consent=form.elements.namedItem('consent').checked;
 if(d.end_date&&d.travel_date&&d.end_date<d.travel_date){statusBox.textContent='La fecha final debe ser igual o posterior a la inicial.';return;}
 if(!submissionId)submissionId=crypto.randomUUID();
 document.querySelector('#send').disabled=true;statusBox.textContent='Guardando tus datos…';
 try{await call('/solicitud/submit',{token,submission_id:submissionId,details:d});success();}
 catch(error){statusBox.textContent=error.message;}
 finally{document.querySelector('#send').disabled=false;}
});
init();
