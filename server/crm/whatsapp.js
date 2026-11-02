'use strict';
const $=s=>document.querySelector(s);let selected=null,timer=null,busy=false,eventOffset=0;
function el(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
async function api(path,method='GET',body){const r=await fetch(path,{method,credentials:'same-origin',headers:method==='GET'?{}:{'Content-Type':'application/json','X-ROMA-Panel':'1'},body:method==='GET'?undefined:JSON.stringify(body||{})});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Revisá los campos de la solicitud');return data;}
async function action(fn){if(busy)return;busy=true;$('#message').textContent='Procesando…';try{await fn();$('#message').textContent='Operación completada.';}catch(e){$('#message').textContent=e.message;}finally{busy=false;}}
async function accounts(){const list=await api('/api/whatsapp/accounts');$('#accounts').replaceChildren();for(const a of list){const card=el('div');card.className='card';card.append(el('h3',a.label),el('p',a.status));const controls=el('div');controls.className='actions';for(const [label,op]of [['Conectar','start'],['Ver QR / grupos','view'],['Pausar','pause'],['Desvincular','logout']]){const b=el('button',label);b.onclick=()=>action(async()=>{if(op==='logout'&&!confirm('Se eliminará la sesión local. Revisá también los dispositivos vinculados en el teléfono. ¿Continuar?'))return;if(op!=='view')await api('/api/whatsapp/accounts/'+a.id+'/'+op,'POST');selected=a.id;$('#account-title').textContent=a.label;$('#connection').hidden=false;$('#groups-form').hidden=true;$('#qr').hidden=true;clearInterval(timer);await qr();timer=setInterval(()=>qr().catch(e=>$('#account-status').textContent=e.message),5000);await accounts();});controls.append(b);}card.append(controls);$('#accounts').append(card);}}
async function qr(){if(!selected)return;const id=selected;const d=await api('/api/whatsapp/accounts/'+id+'/qr');if(selected!==id)return;$('#account-status').textContent=d.status;$('#qr').hidden=!d.qr;$('#qr-help').hidden=d.status==='conectada';if(d.qr&&d.qr.startsWith('data:image/png;base64,'))$('#qr').src=d.qr;else $('#qr').removeAttribute('src');}
async function groups(){const id=selected;const [list,cfg]=await Promise.all([api('/api/whatsapp/accounts/'+id+'/groups'),api('/api/whatsapp/accounts/'+id+'/config')]);if(id!==selected)return;$('#internal').replaceChildren();const empty=el('option','Sin avisos internos por ahora');empty.value='';$('#internal').append(empty);$('#sources').replaceChildren();for(const g of list){const option=el('option',g.name);option.value=g.id;option.selected=cfg.internal_group===g.id;$('#internal').append(option);const label=el('label');label.className='group-option';const input=el('input');input.type='checkbox';input.value=g.id;input.checked=cfg.sources.some(s=>s.group_id===g.id);label.append(input,document.createTextNode(g.name+' · '+g.id));$('#sources').append(label);}$('#groups-form').hidden=false;}
const categoryNames={transfer:'Transfer aeroportuario',traslado:'Traslado',alojamiento_yala:'Alojamiento · Yala',alojamiento_carmen:'Alojamiento · El Carmen',alquiler_vehiculo:'Alquiler de vehículo',actividad:'Excursión / actividad',ticket:'Ticket',paquete:'Paquete',otro:'Por clasificar'};
const dirtyForms=new Set();
window.addEventListener('beforeunload',e=>{if(dirtyForms.size){e.preventDefault();e.returnValue='';}});
function fichaEditor(r,card){
 const details=el('details');details.className='ficha';details.open=false;
 details.append(el('summary','Ficha, datos faltantes y respuesta · '+r.code));card.append(details);
 const form=el('form'),grid=el('div');grid.className='ficha-grid';form.append(grid);details.append(form);
 const controls={};let version=r.ficha_version,enquiryVersion=r.enquiry_version,current={...(r.ficha||{})},revision=0,previewTimer;
 const info=el('p',''),missingBox=el('div');missingBox.className='missing-box';missingBox.setAttribute('aria-live','polite');
 const draft=el('textarea');draft.value=r.draft||'';draft.maxLength=6000;draft.rows=7;
 const saved=el('p',r.ficha?'Ficha guardada. Revisá los datos antes de contactar.':'Esta captura anterior todavía no tiene ficha. Podés extraer los datos del original.');saved.setAttribute('role','status');
 const open=el('a','Abrir WhatsApp con respuesta');open.className='whatsapp-button';open.target='_blank';open.rel='noopener noreferrer';
 const actions=el('div');actions.className='actions';
 const requestBox=el('section');requestBox.className='passenger-request';card.insertBefore(requestBox,details);
 const requestTitle=el('h4','Formulario para que complete el pasajero');requestBox.append(requestTitle);
 const requestInfo=el('p','Generá un enlace individual con los datos guardados. El pasajero lo completa desde su celular, sin VPN.');requestBox.append(requestInfo);
 const generateLink=el('button','Solicitar datos al pasajero');generateLink.type='button';requestBox.append(generateLink);
 const requestOutput=el('div');requestBox.append(requestOutput);
 function field(key,label,type='text'){
  const wrap=el('label',label),input=el('input');input.type=type;
  if(type==='checkbox')input.checked=!!current[key];else input.value=current[key]??'';
  if(type==='number'){input.min=1;input.max=500;input.step=1;}
  if(type==='text')input.maxLength=key==='extra_question'?1000:key==='name'?120:key==='phone'?16:200;
  if(key==='flight')input.maxLength=80;
  if(key==='phone')input.placeholder='+5493881234567';
  wrap.append(input);grid.append(wrap);controls[key]=input;
 }
 const catWrap=el('label','Servicio'),cat=el('select');for(const [key,name]of Object.entries(categoryNames)){const option=el('option',name);option.value=key;cat.append(option);}cat.value=current.category||'otro';catWrap.append(cat);grid.append(catWrap);controls.category=cat;
 for(const [key,label,type]of [
  ['name','Nombre del autor'],['phone','WhatsApp con código de país (+…)'],['contact_confirmed','Revisé que este teléfono corresponde al destinatario','checkbox'],
  ['passengers','Cantidad de pasajeros','number'],['origin','Origen / punto de retiro'],['destination','Destino / devolución'],
  ['travel_date','Fecha propuesta / inicio','date'],['end_date','Fecha final','date'],['date_confirmed','Fecha(s) confirmada(s) con el pasajero','checkbox'],
  ['time','Horario','time'],['flight','Número de vuelo'],['luggage','Equipaje'],['activity','Actividad / recorrido'],
  ['extra_question','Otra duda para consultar al pasajero']
 ])field(key,label,type||'text');
 function values(){const f={...current};for(const [k,c]of Object.entries(controls))f[k]=c.type==='checkbox'?c.checked:c.type==='number'?(c.value?Number(c.value):null):c.type==='date'?(c.value||null):c.value;return f;}
 function disableLink(){open.removeAttribute('href');open.setAttribute('aria-disabled','true');}
 function linkFor(f,text){disableLink();if(f.contact_confirmed&&/^\+[1-9][0-9]{7,14}$/.test(f.phone||'')&&text.trim()){open.href='https://wa.me/'+f.phone.slice(1)+'?text='+encodeURIComponent(text);open.setAttribute('aria-disabled','false');}}
 open.addEventListener('click',e=>{if(open.getAttribute('aria-disabled')==='true'){e.preventDefault();return;}if(!confirm('Abrir WhatsApp para '+controls.phone.value+' con el borrador guardado. Revisá el destinatario y pulsá Enviar allí.'))e.preventDefault();});
 function markDirty(){generateLink.disabled=true;revision++;dirtyForms.add(r.event_id);disableLink();saved.textContent='Cambios sin guardar. Guardá la ficha y el borrador antes de abrir WhatsApp.';}
 function showMissing(data){missingBox.replaceChildren(el('strong','Datos por completar o confirmar'));if(!data.missing.length)missingBox.append(el('p','Datos básicos completos. Verificar tarifa y disponibilidad antes de cotizar.'));else{const list=el('ul');for(const item of data.missing)list.append(el('li',item.label));missingBox.append(list);}if(!controls.phone.value)missingBox.append(el('p','Contacto pendiente: completá el teléfono si está disponible.'));else if(!controls.contact_confirmed.checked)missingBox.append(el('p','Revisá el destinatario antes de habilitar WhatsApp.'));}
 async function preview(){const snapshot=revision;try{const d=await api('/api/whatsapp/preview','POST',values());if(snapshot===revision)showMissing(d);}catch(e){if(snapshot===revision)missingBox.textContent=e.message;}}
 form.addEventListener('input',e=>{if(e.target===controls.phone)controls.contact_confirmed.checked=false;if([controls.travel_date,controls.end_date].includes(e.target))controls.date_confirmed.checked=false;markDirty();clearTimeout(previewTimer);previewTimer=setTimeout(preview,350);});
 info.textContent='Autor registrado: '+(r.sender_name||'Sin nombre')+' · Teléfono recibido: '+(r.sender_phone||'No disponible')+' · Fuente: '+(r.phone_source||'Sin correspondencia telefónica')+'. Las fechas extraídas son propuestas.';
 const originalDate=el('p','Referencia de fecha: '+(current.date_text||'No detectada')+(current.notes?' · '+current.notes:''));
 form.append(info,originalDate,missingBox);
 const draftLabel=el('label','Respuesta editable (se guarda al pulsar Guardar)');draftLabel.append(draft);form.append(draftLabel);
 const extract=el('button','Extraer del mensaje original');extract.type='button';extract.onclick=()=>action(async()=>{
  if(!confirm('Reemplazar los campos y el borrador de esta ficha con una nueva extracción del mensaje original. No se guardará hasta pulsar Guardar.'))return;
  const d=await api('/api/whatsapp/events/'+r.event_id+'/extract','POST');current=d.ficha;
  for(const [k,c]of Object.entries(controls)){if(c.type==='checkbox')c.checked=!!current[k];else c.value=current[k]??'';}
  draft.value=d.draft;originalDate.textContent='Referencia de fecha: '+(current.date_text||'No detectada')+(current.notes?' · '+current.notes:'');markDirty();showMissing(d);
 });
 const generate=el('button','Preparar pregunta con datos faltantes');generate.type='button';generate.onclick=()=>action(async()=>{
  if(draft.value.trim()&&!confirm('Reemplazar el borrador con una pregunta basada en los campos actuales y la duda adicional.'))return;
  const d=await api('/api/whatsapp/preview','POST',values());draft.value=d.draft;markDirty();showMissing(d);
 });
 const save=el('button','Guardar ficha y borrador');save.type='submit';
 form.onsubmit=e=>{e.preventDefault();action(async()=>{
  const snapshot=revision;const d=await api('/api/whatsapp/events/'+r.event_id+'/ficha','PUT',{version,enquiry_version:enquiryVersion,ficha:values(),draft:draft.value});
  version=d.ficha_version;enquiryVersion=d.enquiry_version;
  if(snapshot===revision){current=d.ficha;generateLink.disabled=r.request_status==='received';dirtyForms.delete(r.event_id);saved.textContent='Ficha y borrador guardados. Abrir WhatsApp no envía el mensaje automáticamente.';linkFor(d.ficha,d.draft);showMissing(d);}
  else saved.textContent='Se guardó la versión enviada; hay nuevos cambios sin guardar.';
 });};
 actions.append(extract,generate,save,open);form.append(actions,saved);
 generateLink.disabled=!r.ficha||r.request_status==='received';
 if(!r.ficha)requestInfo.textContent='Primero abrí la ficha, extraé los datos del original y guardala. Después podrás generar el formulario.';
 if(r.request_status){
  const labels={awaiting:'Faltan datos · enlace emitido',received:'Datos recibidos · pendientes de revisión',reviewed:'Datos revisados · comprobar tarifa y disponibilidad',revoked:'Enlace anulado'};
  requestInfo.textContent=(r.request_status==='awaiting'&&new Date(r.request_expires_at)<new Date()?'Enlace vencido':labels[r.request_status]||r.request_status)+(r.request_expires_at?' · Vencimiento: '+new Date(r.request_expires_at).toLocaleString('es-AR',{timeZone:'America/Argentina/Jujuy'}):'');
 }
 if(r.passenger_response){
  const responseDetails=el('details'),summary=el('summary','Ver datos enviados por el pasajero');responseDetails.append(summary);
  const labels={name:'Nombre',phone:'WhatsApp',passengers:'Pasajeros',origin:'Origen',destination:'Destino',travel_date:'Fecha inicial',end_date:'Fecha final',time:'Horario',flight:'Vuelo',luggage:'Equipaje',activity:'Actividad',answer:'Respuesta a la duda',comments:'Observaciones'};
  if(r.request_snapshot?.extra_question)responseDetails.append(el('p','Pregunta enviada: '+r.request_snapshot.extra_question));
  for(const [key,label]of Object.entries(labels)){const value=r.passenger_response[key];if(value)responseDetails.append(el('p',label+': '+value));}
  requestBox.append(responseDetails);
  if(r.request_status==='received'){
   const apply=el('button','Revisé los datos: aplicar a la ficha');apply.type='button';requestBox.append(apply);
   apply.onclick=()=>action(async()=>{
    if(dirtyForms.size)throw Error('Guardá o descartá los cambios locales antes de aplicar la respuesta.');
    if(!confirm('Aplicar los datos enviados por el pasajero a esta ficha y generar un nuevo borrador. Revisá primero las observaciones y el teléfono.'))return;
    await api('/api/whatsapp/events/'+r.event_id+'/request/'+r.request_id+'/apply','POST',{version,enquiry_version:enquiryVersion});await events();
   });
  }
 }
 if(r.request_status==='awaiting'){
  const revoke=el('button','Anular enlace anterior');revoke.type='button';revoke.className='secondary';requestBox.append(revoke);
  revoke.onclick=()=>action(async()=>{await api('/api/whatsapp/events/'+r.event_id+'/request/'+r.request_id+'/revoke','POST');await events();});
 }
 generateLink.onclick=()=>action(async()=>{
  if(dirtyForms.has(r.event_id))throw Error('Guardá primero la ficha y el borrador.');
  if(r.request_status==='awaiting'&&!confirm('Crear un nuevo enlace anula el anterior. ¿Continuar?'))return;
  const d=await api('/api/whatsapp/events/'+r.event_id+'/request','POST',{version,enquiry_version:enquiryVersion});r.request_status='awaiting';r.request_id=d.id;
  requestOutput.replaceChildren();requestInfo.textContent='Enlace creado. Vence en 7 días. Compartilo únicamente con el pasajero.';
  const text=el('textarea');text.value=d.message;text.readOnly=true;text.setAttribute('aria-label','Mensaje con enlace al formulario');requestOutput.append(text);
  const copy=el('button','Copiar mensaje y enlace');copy.type='button';copy.onclick=async()=>{text.focus();text.select();try{await navigator.clipboard.writeText(text.value);requestInfo.textContent='Mensaje copiado.';}catch{requestInfo.textContent='Texto seleccionado: presioná Ctrl+C o mantené pulsado para copiar.';}};requestOutput.append(copy);
  if(current.contact_confirmed&&/^\+[1-9][0-9]{7,14}$/.test(current.phone||'')){
   const sendLink=el('a','Compartir formulario por WhatsApp');sendLink.className='whatsapp-button';sendLink.href='https://wa.me/'+current.phone.slice(1)+'?text='+encodeURIComponent(d.message);sendLink.target='_blank';sendLink.rel='noopener noreferrer';requestOutput.append(sendLink);
  }else requestOutput.append(el('p','Copiá este mensaje al chat del pasajero. También podés revisar y guardar su teléfono en la ficha.'));
  const openForm=el('a','Ver formulario generado');openForm.href=d.url;openForm.target='_blank';openForm.rel='noopener noreferrer';requestOutput.append(openForm);
  requestOutput.append(el('p','Guardá el mensaje si lo vas a compartir más tarde. Al actualizar el panel, este enlace no se vuelve a mostrar; generar otro anula el anterior.'));
 });
 if(r.ficha)linkFor(current,draft.value);else disableLink();
 preview();
}
async function events(){
 if(dirtyForms.size&&!confirm('Hay cambios sin guardar. ¿Descartarlos y actualizar las capturas?'))return;
 const rows=await api('/api/whatsapp/events?filter='+encodeURIComponent($('#event-filter').value)+'&code='+encodeURIComponent($('#event-code').value.trim())+'&limit=50&offset='+eventOffset);dirtyForms.clear();$('#events').replaceChildren();
 for(const r of rows){const card=el('article');card.className='card';card.append(el('h3',(r.code||'Por revisar')+' · '+r.group_name),el('p',new Date(r.source_at).toLocaleString('es-AR',{timeZone:'America/Argentina/Jujuy'})+' · '+(r.classification||'pendiente')+' · Aviso: '+r.delivery_status),el('pre',r.text));if(r.code)fichaEditor(r,card);else{const promote=el('button','Es una consulta turística: crear ficha');promote.onclick=()=>action(async()=>{await api('/api/whatsapp/events/'+r.event_id+'/promote','POST');$('#event-filter').value='consultas';eventOffset=0;await events();});card.append(promote);}$('#events').append(card);}
 $('#events-prev').disabled=eventOffset===0;$('#events-next').disabled=rows.length<50;$('#events-page').textContent='Página '+(eventOffset/50+1);
 if(!rows.length)$('#events').append(el('p','No hay capturas para este filtro.'));
}
$('#new-account').onsubmit=e=>{e.preventDefault();action(async()=>{await api('/api/whatsapp/accounts','POST',{label:$('#label').value});$('#label').value='';await accounts();});};
$('#refresh').onclick=()=>action(accounts);$('#get-groups').onclick=()=>action(groups);
$('#groups-form').onsubmit=e=>{e.preventDefault();action(async()=>{await api('/api/whatsapp/accounts/'+selected+'/config','POST',{internal_group:$('#internal').value,sources:Array.from($('#sources').querySelectorAll('input:checked'),x=>x.value)});});};
$('#process').onclick=()=>action(async()=>{await api('/api/whatsapp/process','POST');await events();});
$('#dispatch').onclick=()=>action(async()=>{await api('/api/whatsapp/dispatch','POST');await events();});
$('#event-code').value=new URLSearchParams(location.search).get('code')||'';
$('#find-event').onclick=()=>action(async()=>{eventOffset=0;await events();});
$('#refresh-events').onclick=()=>action(events);
$('#event-filter').onchange=()=>action(async()=>{eventOffset=0;await events();});
$('#events-prev').onclick=()=>action(async()=>{eventOffset=Math.max(0,eventOffset-50);await events();});
$('#events-next').onclick=()=>action(async()=>{eventOffset+=50;await events();});
action(async()=>{await accounts();await events();});
