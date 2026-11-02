import {createCipheriv,createDecipheriv,randomBytes,timingSafeEqual,createHash} from 'node:crypto';
export function authorized(header,token){const a=Buffer.from(header||''),b=Buffer.from('Bearer '+token);return token.length>=32&&a.length===b.length&&timingSafeEqual(a,b);}
export function encrypt(text,key){const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',Buffer.from(key,'hex'),iv);return Buffer.concat([iv,c.update(text),c.final(),c.getAuthTag()]).toString('base64');}
export function decrypt(text,key){const b=Buffer.from(text,'base64'),c=createDecipheriv('aes-256-gcm',Buffer.from(key,'hex'),b.subarray(0,12));c.setAuthTag(b.subarray(-16));return Buffer.concat([c.update(b.subarray(12,-16)),c.final()]).toString();}
export const digest=text=>createHash('sha256').update(text).digest('hex');
export const validGroup=id=>typeof id==='string'&&/^[0-9-]+@g\.us$/.test(id);
export function extractText(m){if(!m||m.protocolMessage||m.viewOnceMessage||m.viewOnceMessageV2||m.ephemeralMessage)return '';return (m.conversation||m.extendedTextMessage?.text||'').trim().slice(0,5000);}
export function eligible(m,type,sources,internals){return type==='notify'&&!m.key?.fromMe&&validGroup(m.key?.remoteJid)&&sources.has(m.key.remoteJid)&&!internals.has(m.key.remoteJid)&&!!m.key?.id&&!!extractText(m.message);}

// A LID is not a telephone number. Never turn its numeric part into a wa.me URL.
export function phoneFromJid(jid){
 if(typeof jid!=='string')return '';
 const m=jid.match(/^([1-9][0-9]{7,14})(?::[0-9]+)?@s\.whatsapp\.net$/);
 return m?'+'+m[1]:'';
}
export async function authorContact(key, lookup){
 for(const [value,source]of [[key?.participant,'participant'],[key?.participantAlt,'participant_alt']]){
  const phone=phoneFromJid(value);if(phone)return {sender_phone:phone,phone_source:source};
 }
 if(key?.participant?.endsWith('@lid')&&lookup){
  try{const phone=phoneFromJid(await lookup(key.participant));if(phone)return {sender_phone:phone,phone_source:'lid_mapping'};}catch{}
 }
 return {sender_phone:'',phone_source:''};
}
