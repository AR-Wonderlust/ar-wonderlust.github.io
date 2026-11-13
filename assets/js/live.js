'use strict';
// The calendar defines scheduled broadcasts; no streaming-platform detection.
const ROMA_LIVE_HOSTS = {
 'instagram.com':'instagram','www.instagram.com':'instagram',
 'tiktok.com':'tiktok','www.tiktok.com':'tiktok','vm.tiktok.com':'tiktok','vt.tiktok.com':'tiktok',
 'youtube.com':'youtube','www.youtube.com':'youtube','m.youtube.com':'youtube','youtu.be':'youtube',
 'x.com':'x','www.x.com':'x','twitter.com':'x','www.twitter.com':'x'
};
function activeRomaLives(events, now){
 if(!Array.isArray(events)||!Number.isFinite(now))return [];
 const selected=new Map();
 for(const item of events){
  try{
   const u=new URL(item.url),start=Date.parse(item.start),end=Date.parse(item.end);
   if(u.protocol!=='https:'||u.username||u.password||(u.port&&u.port!=='443')||u.pathname==='/'||!ROMA_LIVE_HOSTS[u.hostname]||ROMA_LIVE_HOSTS[u.hostname]!==item.platform||!(start<=now&&now<end))continue;
   const prior=selected.get(item.platform);
   if(!prior||start>Date.parse(prior.start))selected.set(item.platform,item);
  }catch{}
 }
 return [...selected.values()].sort((a,b)=>a.platform.localeCompare(b.platform));
}
if(typeof module!=='undefined')module.exports={activeRomaLives};
if(typeof document!=='undefined')(()=>{
 const api=window.ROMA_CONFIG?.api_url,nav=document.querySelector('.social-links');
 if(!api||!nav)return;
 const labels={instagram:'Instagram',tiktok:'TikTok',youtube:'YouTube',x:'X'};
 const links=[...nav.querySelectorAll('a')].map(a=>({node:a,url:a.href,text:a.textContent,label:a.getAttribute('aria-label'),platform:ROMA_LIVE_HOSTS[new URL(a.href).hostname]}));
 const banner=document.createElement('div');banner.className='live-broadcast wrap';banner.hidden=true;banner.setAttribute('aria-label','Transmisiones programadas ahora');nav.after(banner);
 let snapshot=null,received=0,receivedWall=0,signature='',pending=false;
 function clear(){snapshot=null;render();}
 function render(){
  const elapsed=performance.now()-received;
  const fresh=snapshot?.status==='ok'&&elapsed>=0&&elapsed<45000&&Date.now()-receivedWall<45000;
  const active=fresh?activeRomaLives(snapshot.events,Date.parse(snapshot.server_now)+elapsed):[];
  const next=JSON.stringify(active.map(e=>[e.platform,e.url,e.title,e.end]));
  if(next===signature)return;signature=next;
  for(const link of links){
   const event=active.find(e=>e.platform===link.platform);link.node.classList.toggle('is-live',!!event);
   link.node.href=event?event.url:link.url;link.node.textContent=event?`${link.text.replace(/\s*↗$/,'')} · 🔴 EN VIVO ↗`:link.text;
   if(event)link.node.setAttribute('aria-label',`${labels[event.platform]}: vivo programado ahora. ${event.title||''}`);
   else if(link.label!==null)link.node.setAttribute('aria-label',link.label);else link.node.removeAttribute('aria-label');
  }
  banner.replaceChildren();banner.hidden=!active.length;
  for(const event of active){
   const a=document.createElement('a');a.href=event.url;a.target='_blank';a.rel='noopener noreferrer';
   a.textContent='🔴 ROMA está en vivo · Ver transmisión ↗'+(active.length>1?' · '+labels[event.platform]:'');
   a.title=`${event.title||labels[event.platform]} · Horario programado en el calendario de ROMA`;
   banner.append(a);
  }
 }
 async function refresh(){
  if(pending||document.hidden)return;pending=true;
  try{
   const response=await fetch(api.replace(/\/$/,'')+'/live',{cache:'no-store',signal:AbortSignal.timeout(8000)});
   if(!response.ok)throw Error('live');const data=await response.json();
   if(data.status!=='ok'||!Array.isArray(data.events)||!Number.isFinite(Date.parse(data.server_now)))throw Error('live');
   if(document.hidden){clear();return;}
   snapshot=data;received=performance.now();receivedWall=Date.now();render();
  }catch{clear();}finally{pending=false;}
 }
 document.addEventListener('visibilitychange',()=>{clear();if(!document.hidden)refresh();});
 window.addEventListener('offline',clear);window.addEventListener('online',refresh);
 setInterval(refresh,30000);setInterval(render,1000);refresh();
})();
