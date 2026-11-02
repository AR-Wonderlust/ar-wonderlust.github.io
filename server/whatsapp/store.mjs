import {DatabaseSync} from 'node:sqlite';
import {mkdirSync} from 'node:fs';
import {encrypt,decrypt} from './core.mjs';
export function openStore(folder,key){
 mkdirSync(folder,{recursive:true,mode:0o700});
 const db=new DatabaseSync(folder+'/bridge.sqlite');
 db.exec(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;
 CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,label TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,internal_group TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS sources(group_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,name TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS auth(account_id TEXT,key TEXT,value TEXT,PRIMARY KEY(account_id,key));
 CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY,account_id TEXT NOT NULL,body TEXT NOT NULL,created_at INTEGER NOT NULL,acked INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY,hash TEXT NOT NULL,status TEXT NOT NULL,provider_id TEXT,created_at INTEGER NOT NULL);
 UPDATE deliveries SET status='unknown' WHERE status='sending';`);
 return {db,put(account,k,v){db.prepare('INSERT OR REPLACE INTO auth VALUES(?,?,?)').run(account,k,encrypt(v,key));},get(account,k){const r=db.prepare('SELECT value FROM auth WHERE account_id=? AND key=?').get(account,k);return r?decrypt(r.value,key):null;},drop(account,k){db.prepare('DELETE FROM auth WHERE account_id=? AND key=?').run(account,k);},seal:s=>encrypt(s,key),unseal:s=>decrypt(s,key)};
}
