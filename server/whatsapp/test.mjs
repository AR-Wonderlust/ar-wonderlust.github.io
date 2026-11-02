import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {spawn} from 'node:child_process';
import {authorized,encrypt,decrypt,eligible,extractText} from './core.mjs';
import {openStore} from './store.mjs';
const key='ab'.repeat(32);
test('secrets: authentication, randomized encryption and tampering',()=>{
 assert.equal(authorized('Bearer '+key,key),true);
 assert.equal(authorized('Bearer wrong',key),false);
 const ciphertext=encrypt('secret session',key);
 assert.notEqual(ciphertext,encrypt('secret session',key));
 assert.equal(decrypt(ciphertext,key),'secret session');
 const modified=Buffer.from(ciphertext,'base64');modified[15]^=1;
 assert.throws(()=>decrypt(modified.toString('base64'),key));
});
test('only selected incoming new group text, excluding internal and disappearing messages',()=>{
 const m={key:{remoteJid:'123@g.us',id:'m1',fromMe:false},message:{conversation:'Busco transfer'}};
 const sources=new Set(['123@g.us']);
 assert.equal(eligible(m,'notify',sources,new Set()),true);
 for(const [message,type,selected,internal] of [
  [m,'append',sources,new Set()], [m,'notify',new Set(),new Set()],
  [m,'notify',sources,sources], [{...m,key:{...m.key,fromMe:true}},'notify',sources,new Set()],
  [{...m,key:{...m.key,remoteJid:'123@s.whatsapp.net'}},'notify',sources,new Set()],
  [{...m,message:{ephemeralMessage:{message:m.message}}},'notify',sources,new Set()]
 ])assert.equal(!!eligible(message,type,selected,internal),false);
 assert.equal(extractText({viewOnceMessage:{message:m.message}}),'');
});
test('isolated durable sessions, unique inbox and uncertain delivery after restart',()=>{
 const folder=mkdtempSync(tmpdir()+'/roma-wa-');let s=openStore(folder,key);
 try{
  s.put('a','creds','account A');s.put('b','creds','account B');
  assert.equal(s.get('a','creds'),'account A');assert.equal(s.get('b','creds'),'account B');
  assert.notEqual(s.db.prepare('SELECT value FROM auth LIMIT 1').get().value,'account A');
  for(let i=0;i<2;i++)s.db.prepare('INSERT OR IGNORE INTO inbox VALUES(?,?,?,?,0)').run('event','a',s.seal('text'),1);
  assert.equal(s.db.prepare('SELECT count(*) n FROM inbox').get().n,1);
  s.db.prepare('INSERT INTO deliveries VALUES(?,?,?,?,?)').run('event','hash','sending',null,1);
  s.db.close();s=openStore(folder,key);
  assert.equal(s.get('b','creds'),'account B');
  assert.equal(s.db.prepare('SELECT status FROM deliveries').get().status,'unknown');
 }finally{s.db.close();rmSync(folder,{recursive:true,force:true});}
});
test('connector boots with installed Baileys and protects administration',async t=>{
 const folder=mkdtempSync(tmpdir()+'/roma-wa-http-');
 const child=spawn(process.execPath,['app.mjs'],{cwd:new URL('.',import.meta.url),env:{...process.env,WA_DATA_DIR:folder,WA_BRIDGE_TOKEN:key,WA_SESSION_KEY:key},stdio:'ignore'});
 t.after(async()=>{const closed=new Promise(resolve=>child.once('close',resolve));child.kill();await closed;rmSync(folder,{recursive:true,force:true});});
 let ready=false;
 for(let i=0;i<40;i++){try{ready=(await fetch('http://127.0.0.1:3000/health')).ok;if(ready)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 assert.equal(ready,true);
 const call=(path,method='GET',body)=>fetch('http://127.0.0.1:3000'+path,{method,headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 assert.equal((await fetch('http://127.0.0.1:3000/accounts')).status,401);
 const a=await (await call('/accounts','POST',{label:'QA'})).json();
 assert.ok(a.id);
 assert.equal((await (await call('/accounts')).json())[0].status,'pausada');
 assert.equal((await call('/accounts/'+a.id+'/config','POST',{sources:[],internal_group:''})).status,400);
 assert.equal((await call('/send-alert','POST',{event_id:'a'.repeat(64),text:'Never send without captured event'})).status,400);
});
