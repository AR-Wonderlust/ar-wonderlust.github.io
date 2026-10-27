'use strict';
const cfg = window.ROMA_CONFIG || {};
const $ = s => document.querySelector(s);
const regions = {
 quebrada:['Quebrada de Humahuaca','0/0d/Jujuy-QuebradaDeHumahuaca-P3120108.JPG','Marianocecowski','3.0','Jujuy-QuebradaDeHumahuaca-P3120108.JPG'],
 puna:['Salinas Grandes · Puna','a/a1/Salinas_grandes.jpg','Gonzalo Rivero','3.0','Salinas grandes.jpg'],
 yungas:['Laguna de Yala · Yungas','f/f5/Laguna_de_Yala.jpg','BarbaraY88','4.0','Laguna de Yala.jpg'],
 valles:['Dique La Ciénaga · Valles','c/ce/Dique_La_Ci%C3%A9naga.jpg','Lizcarit05','4.0','Dique La Ciénaga.jpg']
};
function credit(r) {
 const span=document.createElement('span'); span.append(`${r[0]} · Foto: ${r[2]} · `);
 const a=document.createElement('a'); a.href='https://commons.wikimedia.org/wiki/File:'+encodeURIComponent(r[4]);a.textContent='Wikimedia Commons';a.target='_blank';a.rel='noopener';span.append(a,' · ');
 const l=document.createElement('a');l.href=`https://creativecommons.org/licenses/by-sa/${r[3]}/`;l.textContent=`CC BY-SA ${r[3]}`;span.append(l);return span;
}
Object.values(regions).forEach(r=>{const p=document.createElement('p');p.append(credit(r));$('#credits').append(p)});
function selectRegion(key){const r=regions[key];$('#landscape').src='https://upload.wikimedia.org/wikipedia/commons/'+r[1];$('#landscape').alt=r[0];$('#photo-credit').replaceChildren(credit(r));document.querySelectorAll('[data-region]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.region===key)));}
selectRegion('quebrada');
document.querySelectorAll('[data-region]').forEach(b=>b.addEventListener('click',()=>selectRegion(b.dataset.region)));
$('.menu-button').addEventListener('click',e=>{const open=$('#navigation').classList.toggle('open');e.currentTarget.setAttribute('aria-expanded',String(open));});
document.querySelectorAll('#navigation a').forEach(a=>a.addEventListener('click',()=>{$('#navigation').classList.remove('open');$('.menu-button').setAttribute('aria-expanded','false')}));
let history=[],busy=false,step=0;
const questions=['¿En qué fechas pensás venir y cuántos días te quedarías?','¿Cuántas personas viajan? Si vienen chicos, indicá sus edades aproximadas.','¿Desde dónde salen y dónde se alojarían?','¿Buscan excursiones, traslados, alojamiento o una propuesta completa?','¿Prefieren un viaje tranquilo, caminatas o una combinación?','¡Gracias! Podés continuar por WhatsApp con el resumen de tu consulta. El equipo confirmará opciones, tarifas y disponibilidad.'];
function addMessage(role,text){const b=document.createElement('div');b.className='bubble'+(role==='user'?' user':'');b.textContent=text;$('#messages').append(b);$('#messages').scrollTop=$('#messages').scrollHeight;}
function waLink(){const text='Hola, Agencia ROMA. Quisiera organizar mi viaje a Jujuy.'+(history.length?'\n\nConsulta:\n'+history.map(m=>(m.role==='user'?'Viajero: ':'ROMA: ')+m.text).join('\n'):'');return 'https://wa.me/'+String(cfg.whatsapp||'').replace(/\D/g,'')+'?text='+encodeURIComponent(text.slice(-5500));}
function syncWA(){for(const id of ['handoff','contact','floating-wa']){const a=$('#'+id);if(cfg.whatsapp){a.href=waLink();a.hidden=false;}else{a.hidden=true;}}}
function reset(){history=[];step=0;$('#messages').replaceChildren();addMessage('model',cfg.api_url?'¡Hola! Soy el asistente IA de ROMA. ¿Qué lugares te gustaría visitar en Jujuy?':'¡Hola! Esta es una demostración guiada del asistente ROMA. Puedo ayudarte a preparar tu consulta. ¿Qué lugares te gustaría visitar?');syncWA();}
function setBusy(value){busy=value;$('#send').disabled=value;$('#reset').disabled=value;$('#message').disabled=value;document.querySelectorAll('[data-prompt]').forEach(b=>b.disabled=value);$('#chat-status').textContent=value?'Preparando respuesta…':'';}
async function send(text){if(busy||!text.trim())return;const message=text.trim().slice(0,1500);addMessage('user',message);$('#message').value='';setBusy(true);
 try{let reply;if(cfg.api_url){const response=await fetch(cfg.api_url.replace(/\/$/,'')+'/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,history:history.slice(-12)}),signal:AbortSignal.timeout(45000)});if(!response.ok)throw new Error('request');const data=await response.json();if(typeof data.reply!=='string'||!data.reply)throw new Error('empty');reply=data.reply;}else{reply=questions[Math.min(step++,questions.length-1)];}
 history.push({role:'user',text:message},{role:'model',text:reply});addMessage('model',reply);
 }catch{addMessage('model','No pude completar la respuesta. Tu mensaje queda disponible para continuar por WhatsApp. Podés volver a intentarlo.');history.push({role:'user',text:message});}
 finally{setBusy(false);syncWA();if(!$('#chat').hidden)$('#message').focus();}}
$('#chat-form').addEventListener('submit',e=>{e.preventDefault();send($('#message').value)});
document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>send(b.dataset.prompt)));
$('#reset').addEventListener('click',reset);if(cfg.api_url)$('#chat-mode').textContent='Asistente IA de ROMA';reset();
const nowParts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Argentina/Jujuy',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
const part=n=>Number(nowParts.find(p=>p.type===n).value);const today={y:part('year'),m:part('month')-1,d:part('day')};let month=new Date(today.y,today.m,1);
function drawCalendar(){$('#month-label').textContent=month.toLocaleDateString('es-AR',{month:'long',year:'numeric'});const grid=$('#month-grid');grid.replaceChildren();for(const day of ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']){const s=document.createElement('span');s.className='weekday';s.textContent=day;grid.append(s)}const offset=(month.getDay()+6)%7,days=new Date(month.getFullYear(),month.getMonth()+1,0).getDate();for(let i=0;i<offset+days;i++){const s=document.createElement('span');const d=i-offset+1;if(d>0){s.textContent=d;if(today.y===month.getFullYear()&&today.m===month.getMonth()&&today.d===d){s.className='today';s.setAttribute('aria-label',`Hoy, ${d}`)}}grid.append(s)}}
if(cfg.calendar_id){const frame=document.createElement('iframe');const url=new URL('https://calendar.google.com/calendar/embed');url.search=new URLSearchParams({src:cfg.calendar_id,ctz:'America/Argentina/Jujuy',hl:'es',mode:matchMedia('(max-width:650px)').matches?'AGENDA':'MONTH',showTitle:'0'}).toString();frame.src=url;frame.title='Actividades de Agencia ROMA';frame.loading='lazy';$('#calendar').replaceChildren(frame);const a=document.createElement('a');a.href=url.href;a.textContent='Abrir calendario en otra ventana ↗';a.target='_blank';a.rel='noopener';$('#calendar').append(a);}else{drawCalendar();$('#prev-month').onclick=()=>{month.setMonth(month.getMonth()-1);drawCalendar()};$('#next-month').onclick=()=>{month.setMonth(month.getMonth()+1);drawCalendar()};}
function safeURL(s){try{const u=new URL(s);return u.protocol==='https:'?u.href:null}catch{return null}}
if(cfg.maps_url&&safeURL(cfg.maps_url)){$('#maps-link').href=cfg.maps_url;$('#maps-link').hidden=false;}
async function loadReviews(){if(!cfg.api_url)return;try{const res=await fetch(cfg.api_url.replace(/\/$/,'')+'/reviews',{signal:AbortSignal.timeout(15000)});if(!res.ok)return;const data=await res.json();if(!data.reviews?.length)return;$('#reviews').replaceChildren();const brand=document.createElement('p');brand.className='google-brand';brand.textContent='Google Maps';$('#reviews').before(brand);for(const r of data.reviews){const card=document.createElement('article');card.className='review';const author=document.createElement('a');author.textContent=r.author||'Viajero';author.href=safeURL(r.author_url)||safeURL(r.url)||'https://maps.google.com';author.target='_blank';author.rel='noopener';if(safeURL(r.photo)){const img=document.createElement('img');img.src=r.photo;img.alt='';img.loading='lazy';card.append(img)}const stars=document.createElement('p');stars.className='stars';stars.textContent='★'.repeat(Math.max(0,Math.min(5,Math.round(Number(r.rating)||0))))+` · ${r.relative_time||''}`;const p=document.createElement('p');p.textContent=r.text;const link=document.createElement('a');link.textContent='Leer opinión en Google Maps ↗';link.href=safeURL(r.url)||safeURL(data.url)||'https://maps.google.com';link.target='_blank';link.rel='noopener';card.append(author,stars,p,link);$('#reviews').append(card)}if(safeURL(data.url)){$('#maps-link').href=data.url;$('#maps-link').hidden=false;}}catch{/* Se conserva el estado honesto sin reseñas. */}}
loadReviews();


// Non-modal floating assistant: preserve conversation when closing.
const chatPanel = $('#chat');
const chatLauncher = $('#chat-launcher');
let chatOpener = chatLauncher;
function showChat(open, trigger, focusInput = true) {
 if (open && trigger) chatOpener = trigger;
 chatPanel.hidden = !open;
 chatLauncher.setAttribute('aria-expanded', String(open));
 chatLauncher.textContent = open ? (matchMedia('(max-width:700px)').matches ? 'Minimizar asistente −' : 'Cerrar asistente ×') : 'Asistente IA · ROMA';
 if (open && focusInput) { (busy ? $('#chat-close') : $('#message')).focus(); }
 else if (!open && chatOpener?.isConnected) chatOpener.focus();
}
chatLauncher.addEventListener('click', () => showChat(chatPanel.hidden, chatLauncher));
$('#chat-close').addEventListener('click', () => showChat(false));
document.querySelectorAll('a[href="#chat"]').forEach(a => a.addEventListener('click', e => {
 e.preventDefault(); showChat(true, a);
}));
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !chatPanel.hidden) showChat(false); });
if (matchMedia('(max-width:700px)').matches) {
 $('#chat-close').textContent = '−';
 $('#chat-close').setAttribute('aria-label', 'Minimizar asistente');
 // Open without focusing the input: avoid opening the phone keyboard on arrival.
 showChat(true, chatLauncher, false);
} else if (location.hash === '#chat') showChat(true, chatLauncher);
