import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
const {PGlite}=await import(process.env.PGLITE_MODULE||'@electric-sql/pglite');
const db=new PGlite();
try {
 const folder=new URL('../server/crm/migrations/',import.meta.url);
 for(const file of (await readdir(folder)).filter(f=>f.endsWith('.sql')).sort()) await db.exec(await readFile(new URL(file,folder),'utf8'));
 const e=(await db.query("INSERT INTO enquiries(request_id,channel,summary) VALUES('00000000-0000-4000-8000-000000000001','web','Prueba') RETURNING id")).rows[0];
 const r=(await db.query("INSERT INTO transport_rates(fingerprint,snapshot) VALUES('hash','{}') RETURNING id")).rows[0];
 const args=['00000000-0000-4000-8000-000000000002',e.id,r.id];
 const sql="INSERT INTO transport_quotes(request_id,enquiry_id,rate_id,payload,calculation) VALUES($1,$2,$3,'{}','{}') ON CONFLICT(request_id) DO NOTHING RETURNING id";
 const q=(await db.query(sql,args)).rows[0];
 assert.equal((await db.query(sql,args)).rows.length,0);
 await assert.rejects(db.query("UPDATE transport_quotes SET status='aprobado' WHERE id=$1",[q.id]));
 await db.query("UPDATE transport_quotes SET status='aprobado',approved_by='operator',approved_at=now() WHERE id=$1",[q.id]);
 assert.equal((await db.query('SELECT status FROM transport_quotes WHERE id=$1',[q.id])).rows[0].status,'aprobado');
 console.log('OK: migraciones 001–005, relaciones, deduplicación y aprobación');
} finally {await db.close();}
