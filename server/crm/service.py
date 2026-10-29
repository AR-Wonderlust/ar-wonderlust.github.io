from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from crm.db import connection


async def audit(conn, actor, action, entity, entity_id, metadata=None):
    await conn.execute('INSERT INTO audit_log(actor,action,entity,entity_id,metadata) VALUES(%s,%s,%s,%s,%s)',
                       (actor,action,entity,str(entity_id),Jsonb(metadata or {})))


async def capture(body, channel='web'):
    async with connection() as conn:
        row = await (await conn.execute('''INSERT INTO enquiries(request_id,channel,name,contact,summary,travel_start,travel_end,passengers)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(request_id) DO NOTHING RETURNING id,code''',
            (body.request_id,channel,body.name,body.contact,body.summary,body.travel_start,body.travel_end,body.passengers))).fetchone()
        if not row:
            # Return only the opaque reference, never the old enquiry's personal data.
            row = await (await conn.execute('SELECT id,code FROM enquiries WHERE request_id=%s',(body.request_id,))).fetchone()
            return {'code':row['code'], 'created':False}
        for category in set(body.categories):
            await conn.execute('INSERT INTO enquiry_categories VALUES(%s,%s)',(row['id'],category))
        await conn.execute('INSERT INTO automation_events(event_type,entity_id) VALUES(%s,%s)',('enquiry.created',row['id']))
        await audit(conn,'web','create','enquiry',row['id'],{'consent':'follow-up-v1','channel':channel})
        return {'code':row['code'], 'created':True}


async def update_enquiry(enquiry_id, body, actor):
    async with connection() as conn:
        row = await (await conn.execute('''UPDATE enquiries SET status=%s,owner=%s,next_action=%s,follow_up_at=%s,
            loss_reason=%s,name=%s,contact=%s,version=version+1,updated_at=now() WHERE id=%s AND version=%s RETURNING id,version''',
            (body.status,body.owner,body.next_action,body.follow_up_at,body.loss_reason,body.name,body.contact,enquiry_id,body.version))).fetchone()
        if not row: raise HTTPException(409,'La consulta cambió; recargá antes de guardar.')
        await conn.execute('DELETE FROM enquiry_categories WHERE enquiry_id=%s',(enquiry_id,))
        for category in set(body.categories):
            await conn.execute('INSERT INTO enquiry_categories VALUES(%s,%s)',(enquiry_id,category))
        await audit(conn,actor,'update','enquiry',enquiry_id,{'status':body.status,'version':row['version']})
        return row


async def dashboard():
    async with connection() as conn:
        totals=await (await conn.execute('''SELECT count(*) total,
            count(*) FILTER(WHERE status='nueva') nuevas,
            count(*) FILTER(WHERE status='presupuestada') presupuestadas,
            count(*) FILTER(WHERE status='aceptada') aceptadas,
            count(*) FILTER(WHERE status='perdida') perdidas,
            count(*) FILTER(WHERE follow_up_at<now() AND status NOT IN ('perdida','cerrada','aceptada')) vencidas
            FROM enquiries''')).fetchone()
        categories=await (await conn.execute('''SELECT c.code,c.name,count(ec.enquiry_id) total FROM categories c
            LEFT JOIN enquiry_categories ec ON ec.category_code=c.code GROUP BY c.code,c.name ORDER BY total DESC,c.name''')).fetchall()
        months=await (await conn.execute('''SELECT to_char(created_at AT TIME ZONE 'America/Argentina/Jujuy','YYYY-MM') AS "month",
            channel,count(*) total FROM enquiries GROUP BY 1,2 ORDER BY 1 DESC,2 LIMIT 72''')).fetchall()
        pending=await (await conn.execute("SELECT count(*) total FROM catalog_items WHERE status='pendiente'")).fetchone()
        events=await (await conn.execute('SELECT count(*) total FROM automation_events WHERE processed_at IS NULL')).fetchone()
        return dict(totals=totals,categories=categories,months=months,pending_catalog=pending['total'],pending_events=events['total'])


async def list_enquiries(limit, offset):
    async with connection() as conn:
        return await (await conn.execute('''SELECT e.*,ARRAY(SELECT category_code FROM enquiry_categories WHERE enquiry_id=e.id ORDER BY category_code) categories
            FROM enquiries e ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s''',(limit,offset))).fetchall()


async def list_catalog(limit,offset):
    async with connection() as conn:
        return await (await conn.execute('SELECT * FROM catalog_items ORDER BY updated_at DESC,id DESC LIMIT %s OFFSET %s',(limit,offset))).fetchall()


async def create_catalog(body,actor):
    async with connection() as conn:
        row=await (await conn.execute('''INSERT INTO catalog_items(title,category_code,content,starts_on,ends_on,permanent,source_url)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (body.title,body.category_code,body.content,body.starts_on,body.ends_on,body.permanent,body.source_url))).fetchone()
        await audit(conn,actor,'create','catalog',row['id'])
        return row


async def update_catalog(item_id,body,actor):
    async with connection() as conn:
        # Row lock protects concurrent approval of versions of the same source.
        await conn.execute('SELECT pg_advisory_xact_lock(19413002)')
        row=await (await conn.execute('''UPDATE catalog_items SET title=%s,category_code=%s,content=%s,starts_on=%s,ends_on=%s,
            permanent=%s,source_url=%s,status=%s,approved_by=%s,approved_at=%s,version=version+1,updated_at=now()
            WHERE id=%s AND version=%s RETURNING id,version,source_id''',
            (body.title,body.category_code,body.content,body.starts_on,body.ends_on,body.permanent,body.source_url,body.status,
             actor if body.status=='aprobado' else None,datetime.now(ZoneInfo('UTC')) if body.status=='aprobado' else None,item_id,body.version))).fetchone()
        if not row: raise HTTPException(409,'La ficha cambió; recargá antes de guardar.')
        if body.status=='aprobado' and row['source_id']:
            await conn.execute("UPDATE catalog_items SET status='archivado',version=version+1,updated_at=now() WHERE source_id=%s AND id<>%s AND status='aprobado'",(row['source_id'],item_id))
        await audit(conn,actor,body.status,'catalog',item_id,{'version':row['version']})
        return {'id':row['id'],'version':row['version']}


async def catalog_context():
    """Only approved, not-ended activities; dates supplied explicitly to the LLM.

    Deliberately retains the size guard. Query-aware availability/quotes are later modules.
    """
    today=datetime.now(ZoneInfo('America/Argentina/Jujuy')).date()
    async with connection() as conn:
        rows=await (await conn.execute("SELECT title,content,starts_on,ends_on,permanent FROM catalog_items WHERE status='aprobado' AND (permanent OR ends_on>=%s) ORDER BY starts_on NULLS LAST,id LIMIT 51",(today,))).fetchall()
    if not rows: raise HTTPException(503,'No hay fichas aprobadas vigentes.')
    text='Fecha actual en Jujuy: '+today.isoformat()+'\nCalendario informativo; no confirma cupos ni reservas.\n'
    for row in rows:
        period='Servicio permanente' if row['permanent'] else f"Desde {row['starts_on']} hasta {row['ends_on']}"
        text+='\nACTIVIDAD: '+row['title']+'\n'+period+'\n'+row['content']+'\n'
    if len(rows)>50 or len(text)>120000: raise HTTPException(503,'Catálogo aprobado demasiado grande; revisar fichas vigentes.')
    return text


async def claim_events():
    token=uuid4()
    async with connection() as conn:
        rows=await (await conn.execute('''WITH selected AS (SELECT id FROM automation_events WHERE processed_at IS NULL
            AND (lease_until IS NULL OR lease_until<now()) ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 20)
            UPDATE automation_events e SET lease_token=%s,lease_until=now()+interval '5 minutes',attempts=attempts+1
            FROM selected s WHERE e.id=s.id RETURNING e.id,e.event_type,e.entity_id,e.attempts''',(token,))).fetchall()
    return {'lease_token':str(token),'events':rows}


async def acknowledge(event_id,token):
    async with connection() as conn:
        row=await (await conn.execute('''UPDATE automation_events SET processed_at=COALESCE(processed_at,now())
            WHERE id=%s AND lease_token=%s AND (lease_until>now() OR processed_at IS NOT NULL) RETURNING id''',(event_id,token))).fetchone()
        if not row: raise HTTPException(409,'Evento no reclamado o concesión vencida')
        return {'ok':True}
