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
let crmReference='',crmRequest=null;
let history=[],busy=false,fallback=false,fallbackStep=0,fallbackAnswers=[],fallbackInitial='',fallbackExtra='',fallbackLang='es';
const guidedCopy={
 es:{intro:'La IA no está disponible en este momento. Podemos preparar tu consulta para el equipo de ROMA.',questions:['¿Cuántas personas viajan? Indicá adultos y menores, con sus edades aproximadas.','¿Qué días nos visitan y cuántas noches se quedan?','¿Qué excursiones, lugares o servicios les gustaría disfrutar?','¿Desde dónde salen y dónde se alojarían? Si todavía no lo saben, pueden indicarlo.'],labels:['Pasajeros','Fechas y estadía','Excursiones y servicios','Origen y alojamiento'],done:'¡Gracias! Tu consulta está preparada. Tocá «Enviar al WhatsApp», revisá el mensaje y presioná Enviar en WhatsApp. El equipo confirmará opciones, tarifas y disponibilidad.',button:'Enviar al WhatsApp ↗',mode:'ROMA · Consulta guiada',summary:'Resumen de tu consulta',extra:'Agregué tu aclaración al mensaje. Podés enviarlo por WhatsApp.'},
 en:{intro:'AI is temporarily unavailable. We can prepare your enquiry for the ROMA team.',questions:['How many people are travelling? Please include adults and children with approximate ages.','What dates will you visit, and how many nights will you stay?','Which excursions, places or services interest you?','Where will you depart from and stay? You can say if this is still undecided.'],labels:['Travellers','Dates and stay','Excursions and services','Departure and accommodation'],done:'Thank you! Tap “Send enquiry via WhatsApp”, review the message and press Send in WhatsApp. Our team will confirm options, prices and availability.',button:'Send enquiry via WhatsApp ↗',mode:'ROMA · Guided enquiry',summary:'Your enquiry summary',extra:'Your latest clarification was added. You can send the enquiry via WhatsApp.'},
 pt:{intro:'A IA está temporariamente indisponível. Podemos preparar sua consulta para a equipe ROMA.',questions:['Quantas pessoas vão viajar? Informe adultos e crianças com idades aproximadas.','Em quais datas vocês vêm e quantas noites ficarão?','Quais passeios, lugares ou serviços gostariam de conhecer?','De onde vão sair e onde ficarão hospedados? Podem informar se ainda não decidiram.'],labels:['Passageiros','Datas e estadia','Passeios e serviços','Origem e hospedagem'],done:'Obrigado! Toque em “Enviar consulta pelo WhatsApp”, confira a mensagem e pressione Enviar no WhatsApp. A equipe confirmará opções, preços e disponibilidade.',button:'Enviar consulta pelo WhatsApp ↗',mode:'ROMA · Consulta guiada',summary:'Resumo da consulta',extra:'Acrescentei sua última observação. Você pode enviar a consulta pelo WhatsApp.'},
 zh:{intro:'AI暂时无法使用。我们可以先为您整理咨询信息，交给ROMA团队。',questions:['一共有几位旅客？请说明成人和儿童人数，以及儿童的大致年龄。','您计划哪几天来访，住几晚？','您想参加哪些游览活动，去哪些地方，或需要哪些服务？','您从哪里出发，计划住在哪里？尚未确定也可以说明。'],labels:['旅客人数','日期和住宿天数','活动和服务','出发地和住宿'],done:'谢谢！请点击“通过WhatsApp发送咨询”，检查内容后在WhatsApp中点击发送。团队将确认行程、价格和余位。',button:'通过WhatsApp发送咨询 ↗',mode:'ROMA · 咨询向导',summary:'咨询摘要',extra:'已加入您最新的补充说明。您可以通过WhatsApp发送咨询。'}
};
function detectGuidedLanguage(text){if(/[\u3400-\u9fff]/u.test(text))return 'zh';if(/\b(olá|vocês|passeios|quais|quantas|obrigad[oa]|gostaria)\b/iu.test(text))return 'pt';if(/\b(hello|hi|please|would|what|which|we|travel|activities|visit|people)\b/iu.test(text))return 'en';return 'es';}
function guidedSummary(){const c=guidedCopy[fallbackLang];return c.summary+'\n'+fallbackAnswers.map((a,i)=>c.labels[i]+': '+a).join('\n');}
function beginGuided(message){fallback=true;fallbackLang=detectGuidedLanguage(history.filter(m=>m.role==='user').map(m=>m.text).join(' ')+' '+message);fallbackInitial=history.filter(m=>m.role==='user').map(m=>m.text).join('\n');if(fallbackInitial.length>1500)fallbackInitial='[Consulta previa abreviada]\n'+fallbackInitial.slice(0,1400);fallbackStep=0;fallbackAnswers=[];fallbackExtra='';$('#message').maxLength=600;$('#chat-mode').textContent=guidedCopy[fallbackLang].mode;$('#handoff').textContent=guidedCopy[fallbackLang].button;return guidedCopy[fallbackLang].intro+'\n\n'+guidedCopy[fallbackLang].questions[0];}
function guidedReply(message){const c=guidedCopy[fallbackLang];if(fallbackStep<c.questions.length){fallbackAnswers.push(message);fallbackStep++;return fallbackStep<c.questions.length?c.questions[fallbackStep]:guidedSummary()+'\n\n'+c.done;}fallbackExtra=message;return c.extra;}
function addMessage(role,text){const b=document.createElement('div');b.className='bubble'+(role==='user'?' user':'');b.textContent=text;$('#messages').append(b);$('#messages').scrollTop=$('#messages').scrollHeight;}
function waLink(){let text='Hola, Agencia ROMA. Quisiera organizar mi viaje a Jujuy.';if(crmReference)text+='\nReferencia: '+crmReference;if(fallback){text+='\n\nConsulta inicial:\n'+fallbackInitial+'\n\n'+guidedSummary();if(fallbackExtra)text+='\n\nÚltima aclaración: '+fallbackExtra;}else if(history.length){const transcript=history.map(m=>(m.role==='user'?'Viajero: ':'ROMA: ')+m.text).join('\n');text+='\n\nConsulta:\n'+(transcript.length>4800?'[Últimos mensajes]\n'+transcript.slice(-4800):transcript);}return 'https://wa.me/'+String(cfg.whatsapp||'').replace(/\D/g,'')+'?text='+encodeURIComponent(text);}
function syncWA(){for(const id of ['handoff','contact','floating-wa']){const a=$('#'+id);if(cfg.whatsapp){a.href=waLink();a.hidden=false;}else{a.hidden=true;}}}
function reset(){crmReference='';crmRequest=null;if($('#crm-form')){$('#crm-form').reset();$('#crm-save').disabled=false;$('#crm-result').textContent='';}history=[];fallback=false;fallbackStep=0;fallbackAnswers=[];fallbackInitial='';fallbackExtra='';$('#message').maxLength=1500;$('#messages').replaceChildren();$('#chat-mode').textContent=cfg.api_url?'Asistente IA de ROMA':'ROMA · Consulta guiada';$('#handoff').textContent='Enviar al WhatsApp ↗';addMessage('model',cfg.api_url?'¡Hola! Soy el asistente IA de ROMA. ¿Qué lugares te gustaría visitar en Jujuy?':'¡Hola! Podemos preparar tu consulta para el equipo ROMA. ¿Qué lugares te gustaría visitar?');syncWA();}
function setBusy(value){busy=value;$('#send').disabled=value;$('#reset').disabled=value;$('#message').disabled=value;document.querySelectorAll('[data-prompt]').forEach(b=>b.disabled=value);$('#chat-status').textContent=value?'Preparando respuesta…':'';}
async function send(text){if(busy||!text.trim())return;const message=text.trim().slice(0,fallback?600:1500);addMessage('user',message);$('#message').value='';setBusy(true);
 const previous=history.slice(-12);history.push({role:'user',text:message});
 try{let reply;if(fallback){reply=guidedReply(message);}else if(!cfg.api_url){reply=beginGuided(message);}else{try{
 const response=await fetch(cfg.api_url.replace(/\/$/,'')+'/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,history:previous}),signal:AbortSignal.timeout(35000)});
 if(!response.ok)throw new Error('request');const data=await response.json();if(typeof data.reply!=='string'||!data.reply.trim())throw new Error('empty');reply=data.reply;
 }catch{reply=beginGuided(message);}}
 history.push({role:'model',text:reply});addMessage('model',reply);
 }finally{setBusy(false);syncWA();if(!$('#chat').hidden)$('#message').focus();}}
$('#chat-form').addEventListener('submit',e=>{e.preventDefault();send($('#message').value)});
document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>send(b.dataset.prompt)));
$('#reset').addEventListener('click',reset);reset();
const nowParts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Argentina/Jujuy',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
const part=n=>Number(nowParts.find(p=>p.type===n).value);const today={y:part('year'),m:part('month')-1,d:part('day')};let month=new Date(today.y,today.m,1);
function drawCalendar(){$('#month-label').textContent=month.toLocaleDateString('es-AR',{month:'long',year:'numeric'});const grid=$('#month-grid');grid.replaceChildren();for(const day of ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']){const s=document.createElement('span');s.className='weekday';s.textContent=day;grid.append(s)}const offset=(month.getDay()+6)%7,days=new Date(month.getFullYear(),month.getMonth()+1,0).getDate();for(let i=0;i<offset+days;i++){const s=document.createElement('span');const d=i-offset+1;if(d>0){s.textContent=d;if(today.y===month.getFullYear()&&today.m===month.getMonth()&&today.d===d){s.className='today';s.setAttribute('aria-label',`Hoy, ${d}`)}}grid.append(s)}}
if(cfg.calendar_id){const frame=document.createElement('iframe');const url=new URL('https://calendar.google.com/calendar/embed');url.search=new URLSearchParams({src:cfg.calendar_id,ctz:'America/Argentina/Jujuy',hl:'es',mode:matchMedia('(max-width:650px)').matches?'AGENDA':'MONTH',showTitle:'0'}).toString();frame.src=url;frame.title='Actividades de Agencia ROMA';frame.loading='lazy';$('#calendar').replaceChildren(frame);const a=document.createElement('a');a.href=url.href;a.textContent='Abrir calendario en otra ventana ↗';a.target='_blank';a.rel='noopener';$('#calendar').append(a);}else{drawCalendar();$('#prev-month').onclick=()=>{month.setMonth(month.getMonth()-1);drawCalendar()};$('#next-month').onclick=()=>{month.setMonth(month.getMonth()+1);drawCalendar()};}
function safeURL(s){try{const u=new URL(s);return u.protocol==='https:'?u.href:null}catch{return null}}
if(cfg.maps_url&&safeURL(cfg.maps_url)){$('#maps-link').href=cfg.maps_url;$('#maps-link').hidden=false;}
async function loadReviews(){if(!cfg.api_url)return;try{const res=await fetch(cfg.api_url.replace(/\/$/,'')+'/reviews',{signal:AbortSignal.timeout(15000)});if(!res.ok)return;const data=await res.json();if(Number.isFinite(data.rating)&&data.rating>0&&data.rating<=5&&Number.isInteger(data.review_count)&&data.review_count>0){$('#review-rating').textContent=data.rating.toLocaleString('es-AR',{maximumFractionDigits:1})+' / 5 · '+data.review_count.toLocaleString('es-AR')+' opiniones en Google Maps';$('#review-rating').hidden=false;}if(!Array.isArray(data.reviews)||!data.reviews.length)return;$('#reviews-note').textContent='Reseñas de Google Maps, ordenadas por relevancia. Podés consultar más opiniones en la ficha de Google.';$('#reviews').replaceChildren();const brand=document.createElement('p');brand.className='google-brand';brand.textContent='Google Maps';$('#reviews').before(brand);for(const r of data.reviews){const card=document.createElement('article');card.className='review';const author=document.createElement('a');author.textContent=r.author||'Viajero';author.href=safeURL(r.author_url)||safeURL(r.url)||'https://maps.google.com';author.target='_blank';author.rel='noopener';if(safeURL(r.photo)){const img=document.createElement('img');img.src=r.photo;img.alt='';img.loading='lazy';card.append(img)}const stars=document.createElement('p');stars.className='stars';stars.textContent='★'.repeat(Math.max(0,Math.min(5,Math.round(Number(r.rating)||0))))+` · ${r.relative_time||''}`;const p=document.createElement('p');p.textContent=r.text; p.className='review-excerpt';if((r.text||'').length>180){const more=document.createElement('button');more.type='button';more.className='review-more';more.textContent='Leer más';more.setAttribute('aria-expanded','false');more.addEventListener('click',()=>{const expanded=more.getAttribute('aria-expanded')!=='true';more.setAttribute('aria-expanded',String(expanded));p.classList.toggle('expanded',expanded);more.textContent=expanded?'Leer menos':'Leer más';});p.afterMore=more;}const link=document.createElement('a');link.textContent='Leer opinión en Google Maps ↗';link.href=safeURL(r.url)||safeURL(data.url)||'https://maps.google.com';link.target='_blank';link.rel='noopener';card.append(author,stars,p);if(p.afterMore)card.append(p.afterMore);card.append(link);$('#reviews').append(card)}setupReviewCarousel();if(safeURL(data.url)){$('#maps-link').href=data.url;$('#maps-link').hidden=false;}}catch{/* Se conserva el estado honesto sin reseñas. */}}
function setupReviewCarousel(){
 const track=$('#reviews'),region=track.closest('.reviews-carousel'),controls=region.querySelector('.review-controls');
 if(track.children.length<2)return;
 controls.hidden=false;
 const motion=matchMedia('(prefers-reduced-motion: reduce)');
 let paused=motion.matches,hover=false,visible=false;
 const pause=$('#review-pause');
 function label(){pause.textContent=paused?'Reanudar reseñas':'Pausar reseñas';pause.setAttribute('aria-pressed',String(paused));}
 function move(direction){const max=track.scrollWidth-track.clientWidth;if(max<=1)return;const step=track.firstElementChild.getBoundingClientRect().width+16;let left=track.scrollLeft+direction*step;if(direction>0&&track.scrollLeft>=max-2)left=0;if(direction<0&&track.scrollLeft<=2)left=max;track.scrollTo({left:Math.max(0,Math.min(max,left)),behavior:motion.matches?'instant':'smooth'});}
 $('#review-prev').onclick=()=>move(-1);$('#review-next').onclick=()=>move(1);
 pause.onclick=()=>{paused=!paused;label();};label();
 region.addEventListener('mouseenter',()=>hover=true);region.addEventListener('mouseleave',()=>hover=false);
 track.addEventListener('pointerdown',()=>{paused=true;label();});
 motion.addEventListener('change',()=>{paused=motion.matches;label();});
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;},{threshold:0.25}).observe(region);
 setInterval(()=>{if(!paused&&!hover&&visible&&!document.hidden&&!region.contains(document.activeElement))move(1);},6500);
}
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


// Keep the calendar open while visitors interact with its embedded contents.
const calendarDisclosure = $('#calendar-disclosure');
const calendarTrigger = $('#calendar-trigger');
let calendarHoverTimer;
function cancelCalendarHover(){clearTimeout(calendarHoverTimer);}
calendarTrigger.addEventListener('pointerenter',event=>{
 if(event.pointerType==='mouse'&&matchMedia('(hover: hover) and (pointer: fine)').matches){
  calendarHoverTimer=setTimeout(()=>{calendarDisclosure.open=true;},400);
 }
});
calendarTrigger.addEventListener('pointerleave',cancelCalendarHover);
calendarTrigger.addEventListener('pointerdown',cancelCalendarHover);
calendarTrigger.addEventListener('keydown',cancelCalendarHover);
document.querySelectorAll('a[href="#calendario"]').forEach(link=>link.addEventListener('click',()=>{calendarDisclosure.open=true;}));
function openCalendarFromHash(){if(location.hash==='#calendario')calendarDisclosure.open=true;}
window.addEventListener('hashchange',openCalendarFromHash);
openCalendarFromHash();


// Enquiries are saved only after an explicit, optional follow-up request.
if(cfg.api_url){fetch(cfg.api_url.replace(/\/$/,'')+'/crm/status',{signal:AbortSignal.timeout(5000)})
 .then(r=>r.ok?r.json():null).then(d=>{if(d?.enabled)$('#crm-capture').hidden=false;}).catch(()=>{});}
$('#crm-form').addEventListener('submit',async e=>{
 e.preventDefault();const result=$('#crm-result');
 if(!$('#crm-consent').checked)return;
 if(!history.some(m=>m.role==='user')){result.textContent='Primero contanos qué viaje querés organizar.';return;}
 if(busy){result.textContent='Esperá a que termine la respuesta del asistente.';return;}
 if(crmReference)return;
 $('#crm-save').disabled=true;setBusy(true);$('#chat-status').textContent='Guardando tu consulta…';result.textContent='Guardando consulta…';
 if(!crmRequest)crmRequest={request_id:crypto.randomUUID(),summary:new URL(waLink()).searchParams.get('text').slice(0,6000),name:$('#crm-name').value.trim(),contact:$('#crm-contact').value.trim(),categories:['otro'],consent:true};
 try{const r=await fetch(cfg.api_url.replace(/\/$/,'')+'/enquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(crmRequest),signal:AbortSignal.timeout(10000)});
 if(!r.ok)throw Error('save');const data=await r.json();if(!/^CON-\d+$/.test(data.code))throw Error('code');crmReference=data.code;syncWA();
 result.textContent='Consulta '+crmReference+' guardada. El código está incluido en WhatsApp. Las nuevas respuestas del chat se enviarán por WhatsApp, pero no actualizan este resumen guardado.';
 }catch{result.textContent='No pudimos confirmar el registro. Podés reintentar guardar el mismo resumen o continuar por WhatsApp.';$('#crm-save').disabled=false;}
 finally{setBusy(false);}
});
