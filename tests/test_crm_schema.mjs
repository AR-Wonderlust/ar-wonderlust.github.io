import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {PGlite}=await import(process.env.PGLITE_MODULE||'@electric-sql/pglite');
const db=new PGlite();
try{
 await db.exec(await readFile(new URL('../server/crm/migrations/001_initial.sql',import.meta.url),'utf8'));
 assert.equal((await db.query('SELECT count(*) n FROM categories')).rows[0].n,9);
 const id='00000000-0000-4000-8000-000000000001';
 const insert="INSERT INTO enquiries(request_id,channel,summary) VALUES($1,'web','Consulta de prueba') ON CONFLICT(request_id) DO NOTHING RETURNING id,code";
 const first=(await db.query(insert,[id])).rows[0];assert.equal(first.code,'CON-00000001');
 assert.equal((await db.query(insert,[id])).rows.length,0);
 await assert.rejects(db.query("INSERT INTO enquiries(request_id,channel,summary,travel_start,travel_end) VALUES($1,'web','x','2026-11-03','2026-11-01')",['00000000-0000-4000-8000-000000000002']));
 await assert.rejects(db.query("UPDATE enquiries SET status='perdida' WHERE id=$1",[first.id]));
 await db.query("UPDATE enquiries SET status='perdida',loss_reason='Cambio de fechas' WHERE id=$1",[first.id]);
 await assert.rejects(db.query("INSERT INTO catalog_items(title,category_code,content,status) VALUES('Sin fecha','actividad','x','aprobado')"));
 await db.query("INSERT INTO catalog_items(title,category_code,content,status,permanent,approved_by,approved_at) VALUES('Transfer','transfer','Consultar','aprobado',true,'operador',now())");
 await db.query("INSERT INTO catalog_items(title,category_code,content,status,starts_on,ends_on,approved_by,approved_at) VALUES('Pasado','actividad','x','aprobado','2000-01-01','2000-01-02','operador',now())");
 assert.equal((await db.query("SELECT count(*) n FROM catalog_items WHERE status='aprobado' AND (permanent OR ends_on>=CURRENT_DATE)")).rows[0].n,1);
 await db.query("INSERT INTO automation_events(event_type,entity_id) VALUES('enquiry.created',$1)",[first.id]);
 const lease='00000000-0000-4000-8000-000000000003';
 const claim=`WITH selected AS (SELECT id FROM automation_events WHERE processed_at IS NULL AND (lease_until IS NULL OR lease_until<now()) ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 20) UPDATE automation_events e SET lease_token=$1,lease_until=now()+interval '5 minutes',attempts=attempts+1 FROM selected s WHERE e.id=s.id RETURNING e.id`;
 assert.equal((await db.query(claim,[lease])).rows.length,1);
 assert.equal((await db.query(claim,[lease])).rows.length,0);
 assert.equal((await db.query('UPDATE automation_events SET processed_at=now() WHERE lease_token=$1 RETURNING id',[id])).rows.length,0);
 assert.equal((await db.query('UPDATE automation_events SET processed_at=now() WHERE lease_token=$1 RETURNING id',[lease])).rows.length,1);
 console.log('OK: PostgreSQL schema, codes, deduplication, constraints, approved/current catalog, leased outbox and acknowledgment');
}finally{await db.close();}
