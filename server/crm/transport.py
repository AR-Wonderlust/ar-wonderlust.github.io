"""Transport quotes: deterministic Decimal arithmetic; immutable draft snapshots."""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID
import hashlib
import json
from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, model_validator
from psycopg.types.json import Jsonb
from crm.db import connection

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Rate(Strict):
    service: Literal['excursion','traslado','auto']
    green_reference: Decimal = Field(gt=0,le=10000000)
    yellow_standard: Decimal = Field(gt=0,le=10000000)
    red_floor: Decimal = Field(gt=0,le=10000000)
    @model_validator(mode='after')
    def ordered(self):
        if not self.green_reference >= self.yellow_standard >= self.red_floor:
            raise ValueError('Orden de tarifas inválido')
        return self

class Source(Strict):
    spreadsheet_id: Literal['1W55J03Uy1sY15Wj649_JDslyg1vCiBNHDpB5pvjTMS8']
    sheet: Literal['TRANSPORTE-ROMA-2026']
    range: Literal['E1:N3']
    read_at: datetime
    @model_validator(mode='after')
    def timestamp(self):
        if self.read_at.tzinfo is None: raise ValueError('Fecha sin zona horaria')
        age=(datetime.now(timezone.utc)-self.read_at).total_seconds()
        if age < -300 or age > 86400: raise ValueError('Releer Sheets: lectura fuera de las últimas 24 horas')
        return self

class RateInput(Strict):
    source: Source
    rates: list[Rate] = Field(min_length=3,max_length=3)
    @model_validator(mode='after')
    def unique(self):
        if {r.service for r in self.rates} != {'excursion','traslado','auto'}:
            raise ValueError('Se requieren los tres servicios, sin duplicados')
        return self

class Leg(Strict):
    service: Literal['excursion','traslado','auto']
    travel_date: date
    origin: str = Field(min_length=1,max_length=200)
    destination: str = Field(min_length=1,max_length=200)
    vehicle: str = Field(min_length=1,max_length=100)
    passengers: int = Field(ge=1,le=100)
    capacity: int = Field(ge=1,le=100)
    operational_km: Decimal = Field(gt=0,le=20000)
    km_confirmed: bool = False
    negotiated_rate: Decimal | None = Field(default=None,gt=0,le=10000000)

class QuoteInput(Strict):
    request_id: UUID
    enquiry_id: int = Field(gt=0)
    rate_id: int = Field(gt=0)
    legs: list[Leg] = Field(min_length=1,max_length=50)
    extras_amount: Decimal = Field(default=0,ge=0,le=100000000)
    extras_description: str = Field(default='',max_length=1000)
    conditions: str = Field(min_length=1,max_length=3000)
    valid_until: date
    discount_reason: str = Field(default='',max_length=1000)
    multiple_trips: bool = False

class Approval(Strict):
    availability_confirmed: bool
    capacity_and_baggage_confirmed: bool
    tariff_validity_confirmed: bool
    extras_confirmed: bool

def money(n):
    return str(n.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))

def calculate(body, snapshot):
    rates={r['service']:r for r in snapshot['rates']}
    total=Decimal(0); lines=[]; blockers=[]
    for i,leg in enumerate(body.legs,1):
        r=rates[leg.service]; yellow=Decimal(str(r['yellow_standard'])); floor=Decimal(str(r['red_floor']))
        price=leg.negotiated_rate if leg.negotiated_rate is not None else yellow
        if not floor <= price <= yellow: raise ValueError('La tarifa debe quedar entre rojo y amarillo; verde aún no habilitado')
        if price < yellow and not (body.multiple_trips and body.discount_reason.strip()):
            raise ValueError('Descuento: confirmar varios viajes e indicar motivo')
        if leg.passengers > leg.capacity: blockers.append(f'Tramo {i}: pasajeros exceden capacidad')
        if not leg.km_confirmed: blockers.append(f'Tramo {i}: confirmar kilómetros operativos')
        subtotal=Decimal(money(leg.operational_km*price)); total+=subtotal
        lines.append({'number':i,'rate':str(price),'subtotal':money(subtotal)})
    if body.extras_amount and not body.extras_description.strip(): raise ValueError('Describir adicionales')
    return {'currency':'ARS','lines':lines,'subtotal':money(total),'total':money(total+body.extras_amount),
            'blockers':blockers,'driver_included':True,'fuel_included':True,'can_send':False}

def install(app, operator, automation):
    @app.get('/presupuestos',response_class=HTMLResponse,dependencies=[Depends(operator)])
    async def page(): return Path(__file__).with_name('transport.html').read_text()

    @app.get('/transport.js',dependencies=[Depends(operator)])
    async def script(): return Response(Path(__file__).with_name('transport.js').read_text(),media_type='text/javascript')

    @app.post('/automation/transport/rates',dependencies=[Depends(automation)])
    async def import_rates(body:RateInput):
        data=body.model_dump(mode='json'); fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        async with connection() as conn:
            row=await (await conn.execute('INSERT INTO transport_rates(fingerprint,snapshot) VALUES(%s,%s) ON CONFLICT(fingerprint) DO UPDATE SET fingerprint=EXCLUDED.fingerprint RETURNING id',(fingerprint,Jsonb(data)))).fetchone()
        return {'rate_id':row['id'],'status':'importado','can_send':False}

    @app.get('/api/transport/rates',dependencies=[Depends(operator)])
    async def latest():
        async with connection() as conn:
            return await (await conn.execute('SELECT * FROM transport_rates ORDER BY id DESC LIMIT 1')).fetchone()

    @app.get('/api/transport/quotes',dependencies=[Depends(operator)])
    async def listing():
        async with connection() as conn:
            return await (await conn.execute('SELECT q.*,e.code,e.name FROM transport_quotes q JOIN enquiries e ON e.id=q.enquiry_id ORDER BY q.id DESC LIMIT 100')).fetchall()

    @app.post('/api/transport/quotes')
    async def create(body:QuoteInput,actor=Depends(operator)):
        async with connection() as conn:
            rate=await (await conn.execute('SELECT snapshot FROM transport_rates WHERE id=%s',(body.rate_id,))).fetchone()
            enquiry=await (await conn.execute('SELECT id FROM enquiries WHERE id=%s',(body.enquiry_id,))).fetchone()
            if not rate or not enquiry: raise HTTPException(404,'Consulta o tarifas inexistentes')
            try: calc=calculate(body,rate['snapshot'])
            except ValueError as e: raise HTTPException(422,str(e))
            data=body.model_dump(mode='json')
            row=await (await conn.execute('INSERT INTO transport_quotes(request_id,enquiry_id,rate_id,payload,calculation) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(request_id) DO NOTHING RETURNING *',(body.request_id,body.enquiry_id,body.rate_id,Jsonb(data),Jsonb(calc)))).fetchone()
            if not row:
                row=await (await conn.execute('SELECT * FROM transport_quotes WHERE request_id=%s',(body.request_id,))).fetchone()
                if row['payload']!=data: raise HTTPException(409,'La solicitud ya existe con otros datos')
            else:
                await conn.execute("INSERT INTO audit_log(actor,action,entity,entity_id) VALUES(%s,'crear','transport_quote',%s)",(actor,str(row['id'])))
            return row

    @app.post('/api/transport/quotes/{quote_id}/approve')
    async def approve(quote_id:int,body:Approval,actor=Depends(operator)):
        if not all(body.model_dump().values()): raise HTTPException(422,'Confirmar disponibilidad, capacidad, tarifas y adicionales')
        async with connection() as conn:
            row=await (await conn.execute('SELECT * FROM transport_quotes WHERE id=%s FOR UPDATE',(quote_id,))).fetchone()
            if not row: raise HTTPException(404,'Presupuesto inexistente')
            if row['status']=='aprobado': return {'status':'aprobado','can_send':False}
            from zoneinfo import ZoneInfo
            today=datetime.now(ZoneInfo('America/Argentina/Jujuy')).date()
            data=QuoteInput.model_validate(row['payload'])
            if row['calculation']['blockers'] or data.valid_until<today or any(x.travel_date<today for x in data.legs):
                raise HTTPException(422,'Corregir kilómetros, capacidad o fechas creando un nuevo borrador')
            await conn.execute("UPDATE transport_quotes SET status='aprobado',approved_at=now(),approved_by=%s WHERE id=%s",(actor,quote_id))
            await conn.execute("INSERT INTO audit_log(actor,action,entity,entity_id,metadata) VALUES(%s,'aprobar','transport_quote',%s,%s)",(actor,str(quote_id),Jsonb(body.model_dump())))
        return {'status':'aprobado','can_send':False}
