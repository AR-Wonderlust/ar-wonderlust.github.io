import http from 'node:http';
import {randomUUID} from 'node:crypto';
import makeWASocket,{initAuthCreds,BufferJSON,proto,DisconnectReason} from '@whiskeysockets/baileys';
import pino from 'pino';
import QRCode from 'qrcode';
import {authorized,digest,validGroup,eligible,extractText,authorContact} from './core.mjs';
import {openStore} from './store.mjs';
process.umask(0o077);
const token=process.env.WA_BRIDGE_TOKEN||'',key=process.env.WA_SESSION_KEY||'';
if(token.length<32||!/^[a-f0-9]{64}$/.test(key))throw Error('Configurar secretos con setup_whatsapp.py');
const store=openStore(process.env.WA_DATA_DIR||'/data',key),db=store.db;
const sockets=new Map(),status=new Map(),qrs=new Map(),generations=new Map(),retries=new Map(),groupCache=new Map();
const logger=pino({level:'silent'});
const json=v=>JSON.stringify(v,BufferJSON.replacer),parse=s=>JSON.parse(s,BufferJSON.reviver);
function account(id){const a=db.prepare('SELECT * FROM accounts WHERE id=?').get(id);if(!a)throw Error('Cuenta inexistente');return a;}
function pause(id){db.prepare('UPDATE accounts SET enabled=0 WHERE id=?').run(id);generations.set(id,(generations.get(id)||0)+1);sockets.get(id)?.end(new Error('Pausa del operador'));sockets.delete(id);qrs.delete(id);groupCache.delete(id);status.set(id,'pausada');}
async function start(id){
 if(sockets.has(id))return;
 const a=account(id);if(!a.enabled)return;
 const generation=(generations.get(id)||0)+1;generations.set(id,generation);status.set(id,'conectando');
 const credentials=store.get(id,'creds');const creds=credentials?parse(credentials):initAuthCreds();
 const auth={creds,keys:{async get(type,ids){const result={};for(const k of ids){const raw=store.get(id,type+':'+k);if(raw){let v=parse(raw);if(type==='app-state-sync-key')v=proto.Message.AppStateSyncKeyData.fromObject(v);result[k]=v;}}return result;},async set(data){db.exec('BEGIN');try{for(const [type,values]of Object.entries(data))for(const [k,v]of Object.entries(values))v?store.put(id,type+':'+k,json(v)):store.drop(id,type+':'+k);db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}}}};
 const sock=makeWASocket({auth,logger,markOnlineOnConnect:false,syncFullHistory:false,shouldSyncHistoryMessage:()=>false,browser:['ROMA','Chrome','1.0.0']});sockets.set(id,sock);
 sock.ev.on('creds.update',()=>{if(generations.get(id)===generation)store.put(id,'creds',json(creds));});
 sock.ev.on('connection.update',u=>{
  if(generations.get(id)!==generation)return;
  if(u.qr){qrs.set(id,{value:u.qr,at:Date.now()});status.set(id,'requiere_qr');}
  if(u.connection==='open'){qrs.delete(id);status.set(id,'conectada');retries.set(id,0);}
  if(u.connection==='close'){
   sockets.delete(id);qrs.delete(id);const code=u.lastDisconnect?.error?.output?.statusCode;
   const fatal=[DisconnectReason.loggedOut,DisconnectReason.connectionReplaced,DisconnectReason.badSession,DisconnectReason.forbidden].includes(code);
   if(fatal){db.prepare('UPDATE accounts SET enabled=0 WHERE id=?').run(id);status.set(id,'requiere_revision');return;}
   const n=(retries.get(id)||0)+1;retries.set(id,n);status.set(id,n>5?'requiere_revision':'reconectando');
   if(n<=5)setTimeout(()=>{if(generations.get(id)===generation)start(id).catch(()=>status.set(id,'error'));},Math.min(60000,3000*2**n));
  }
 });
 sock.ev.on('messages.upsert',async({messages,type})=>{
  if(generations.get(id)!==generation)return;
  const sources=new Map(db.prepare('SELECT group_id,name FROM sources WHERE account_id=?').all(id).map(r=>[r.group_id,r.name]));
  const internals=new Set(db.prepare("SELECT internal_group FROM accounts WHERE internal_group<>''").all().map(r=>r.internal_group));
  for(const m of messages){
   if(!eligible(m,type,new Set(sources.keys()),internals))continue;
   const ts=Number(m.messageTimestamp);if(!Number.isFinite(ts)||ts<Date.now()/1000-3600||ts>Date.now()/1000+300)continue;
   const eventId=digest(id+'|'+m.key.remoteJid+'|'+(m.key.participant||'')+'|'+m.key.id);
   const contact=await authorContact(m.key,lid=>Promise.race([sock.signalRepository.lidMapping.getPNForLID(lid),new Promise(resolve=>{const timer=setTimeout(()=>resolve(null),1000);timer.unref();})]));
   if(generations.get(id)!==generation)continue;
   const body={...contact,sender_name:String(m.pushName||'').slice(0,120),event_id:eventId,account_id:id,group_id:m.key.remoteJid,group_name:sources.get(m.key.remoteJid),sender_id:m.key.participant||'',message_id:m.key.id,text:extractText(m.message),timestamp:ts};
   db.prepare('INSERT OR IGNORE INTO inbox VALUES(?,?,?,?,0)').run(eventId,id,store.seal(JSON.stringify(body)),Date.now());
  }
 });
}
async function groups(id){if(status.get(id)!=='conectada')throw Error('Cuenta no conectada');const cached=groupCache.get(id);if(cached&&Date.now()-cached.at<60000)return cached.items;const data=await sockets.get(id).groupFetchAllParticipating();const items=Object.values(data).map(g=>({id:g.id,name:String(g.subject||g.id).slice(0,200)}));groupCache.set(id,{at:Date.now(),items});return items;}
function answer(res,code,data){res.writeHead(code,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));}
async function body(req){let s='';for await(const c of req){s+=c;if(Buffer.byteLength(s)>24000)throw Error('Solicitud demasiado grande');}return s?JSON.parse(s):{};}
const server=http.createServer(async(req,res)=>{
 if(req.url==='/health'&&req.method==='GET')return answer(res,200,{ok:true});
 if(!authorized(req.headers.authorization,token))return answer(res,401,{detail:'No autorizado'});
 try{
  const path=new URL(req.url,'http://bridge').pathname;
  if(path==='/accounts'&&req.method==='GET')return answer(res,200,db.prepare('SELECT * FROM accounts ORDER BY label').all().map(a=>({...a,status:status.get(a.id)||'pausada'})));
  if(path==='/accounts'&&req.method==='POST'){
   const b=await body(req);if(typeof b.label!=='string'||!b.label.trim()||b.label.length>80)throw Error('Nombre requerido, máximo 80 caracteres');
   if(db.prepare('SELECT count(*) n FROM accounts').get().n>=10)throw Error('Límite del piloto: 10 cuentas');
   const id=randomUUID();db.prepare('INSERT INTO accounts(id,label) VALUES(?,?)').run(id,b.label.trim());return answer(res,201,{id});
  }
  const match=path.match(/^\/accounts\/([a-f0-9-]{36})\/(start|pause|logout|qr|groups|config)$/);
  if(match){const [,id,action]=match;account(id);
   if(action==='qr'&&req.method==='GET'){const qr=qrs.get(id);return answer(res,200,{status:status.get(id)||'pausada',qr:qr&&Date.now()-qr.at<45000?await QRCode.toDataURL(qr.value):null});}
   if(action==='groups'&&req.method==='GET')return answer(res,200,await groups(id));
   if(action==='config'&&req.method==='GET')return answer(res,200,{sources:db.prepare('SELECT group_id,name FROM sources WHERE account_id=?').all(id),internal_group:account(id).internal_group});
   if(action==='config'&&req.method==='POST'){
    const b=await body(req),available=new Map((await groups(id)).map(g=>[g.id,g.name]));
    if(!Array.isArray(b.sources)||b.sources.length>100||!b.sources.every(g=>validGroup(g)&&available.has(g)))throw Error('Seleccionar grupos disponibles');
    if(b.internal_group!==''&&(!validGroup(b.internal_group)||!available.has(b.internal_group)))throw Error('Destino interno inválido');
    const internals=new Set(db.prepare('SELECT internal_group FROM accounts WHERE id<>?').all(id).map(a=>a.internal_group));internals.add(b.internal_group);
    if(b.sources.some(g=>internals.has(g)))throw Error('Un destino interno no puede ser fuente');
    if(b.internal_group&&db.prepare('SELECT 1 FROM sources WHERE group_id=? AND account_id<>?').get(b.internal_group,id))throw Error('El destino está monitoreado por otra cuenta');
    for(const g of b.sources)if(db.prepare('SELECT 1 FROM sources WHERE group_id=? AND account_id<>?').get(g,id))throw Error('Otra cuenta ya monitorea ese grupo');
    db.exec('BEGIN');try{db.prepare('DELETE FROM sources WHERE account_id=?').run(id);for(const g of new Set(b.sources))db.prepare('INSERT INTO sources VALUES(?,?,?)').run(g,id,available.get(g));db.prepare('UPDATE accounts SET internal_group=? WHERE id=?').run(b.internal_group,id);db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}
    return answer(res,200,{ok:true});
   }
   if(req.method==='POST'&&['start','pause','logout'].includes(action)){
    if(action==='start'){if(status.get(id)==='requiere_revision')throw Error('Desvincular y revisar el teléfono antes de volver a conectar');db.prepare('UPDATE accounts SET enabled=1 WHERE id=?').run(id);await start(id);}
    if(action==='pause')pause(id);
    if(action==='logout'){const sock=sockets.get(id);db.prepare('UPDATE accounts SET enabled=0 WHERE id=?').run(id);generations.set(id,(generations.get(id)||0)+1);try{if(sock)await Promise.race([sock.logout().catch(()=>{}),new Promise(resolve=>setTimeout(resolve,5000))]);}finally{pause(id);db.prepare('DELETE FROM auth WHERE account_id=?').run(id);status.set(id,'pausada');}}
    return answer(res,200,{ok:true});
   }
  }
  if(path==='/send-alert'&&req.method==='POST'){
   const b=await body(req);if(!/^[a-f0-9]{64}$/.test(b.event_id)||typeof b.text!=='string'||b.text.length>9000)throw Error('Aviso inválido');
   const original=db.prepare('SELECT * FROM inbox WHERE id=?').get(b.event_id);if(!original)throw Error('Evento no disponible');
   const event=JSON.parse(store.unseal(original.body)),a=account(original.account_id);
   const hash=digest(b.text),prior=db.prepare('SELECT * FROM deliveries WHERE id=?').get(b.event_id);
   if(prior){if(prior.hash!==hash)throw Error('El aviso cambió');return answer(res,200,{status:prior.status});}
   if(!db.prepare('SELECT 1 FROM sources WHERE group_id=? AND account_id=?').get(event.group_id,a.id))return answer(res,200,{status:'paused'});
   if(!a.internal_group||!a.enabled||status.get(a.id)!=='conectada')return answer(res,200,{status:'pending'});
   if(!(await groups(a.id)).some(g=>g.id===a.internal_group))return answer(res,200,{status:'pending'});
   const current=account(a.id);
   if(!current.enabled||current.internal_group!==a.internal_group||status.get(a.id)!=='conectada'||!db.prepare('SELECT 1 FROM sources WHERE group_id=? AND account_id=?').get(event.group_id,a.id))return answer(res,200,{status:'pending'});
   const raced=db.prepare('SELECT * FROM deliveries WHERE id=?').get(b.event_id);
   if(raced)return answer(res,200,{status:raced.hash===hash?raced.status:'unknown'});
   // Persist before the external side effect. Unknown results are never retried blindly.
   db.prepare("INSERT INTO deliveries VALUES(?,?,'sending',NULL,?)").run(b.event_id,hash,Date.now());
   try{const sent=await sockets.get(a.id).sendMessage(a.internal_group,{text:b.text});db.prepare("UPDATE deliveries SET status='sent',provider_id=? WHERE id=?").run(sent?.key?.id||null,b.event_id);return answer(res,200,{status:'sent'});}
   catch{db.prepare("UPDATE deliveries SET status='unknown' WHERE id=?").run(b.event_id);return answer(res,200,{status:'unknown'});}
  }
  return answer(res,404,{detail:'Ruta inexistente'});
 }catch(e){const safe=['Nombre requerido','Límite del piloto','Cuenta inexistente','Cuenta no conectada','Seleccionar grupos','Destino interno inválido','Un destino interno','El destino está','Otra cuenta','Desvincular','Evento no disponible','El aviso cambió','Aviso inválido','Solicitud demasiado grande'];answer(res,400,{detail:safe.some(s=>e.message.startsWith(s))?e.message:'Operación no completada. Revisá estado y conexión.'});}
});
server.listen(3000,'0.0.0.0');
let pumping=false;
setInterval(async()=>{if(pumping)return;pumping=true;try{for(const row of db.prepare('SELECT * FROM inbox WHERE acked=0 ORDER BY created_at LIMIT 20').all()){
 const r=await fetch('http://crm-admin:8000/integrations/whatsapp/events',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:store.unseal(row.body),signal:AbortSignal.timeout(10000)});
 if(!r.ok)break;db.prepare('UPDATE inbox SET acked=1 WHERE id=?').run(row.id);
 }}catch{console.error('Entrega de eventos pendiente; se reintentará.');}finally{pumping=false;}},5000);
for(const a of db.prepare('SELECT id FROM accounts WHERE enabled=1').all())await start(a.id).catch(()=>status.set(a.id,'error'));
