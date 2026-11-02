"""Conservative, local extraction. Proposed dates always need operator confirmation."""
import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Literal
from pydantic import BaseModel, Field, model_validator, field_validator
from crm.models import Category


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')


class Ficha(BaseModel):
    category: Category = 'otro'
    name: str = Field(default='', max_length=120)
    phone: str = Field(default='', max_length=16, pattern=r'^(?:\+[1-9][0-9]{7,14})?$')
    contact_confirmed: bool = False
    passengers: int | None = Field(default=None, ge=1, le=500)
    origin: str = Field(default='', max_length=200)
    destination: str = Field(default='', max_length=200)
    travel_date: date | None = None
    end_date: date | None = None
    date_confirmed: bool = False
    date_text: str = Field(default='', max_length=200)
    time: str = Field(default='', pattern=r'^(?:[0-2][0-9]:[0-5][0-9])?$', max_length=5)
    flight: str = Field(default='', max_length=80)
    luggage: str = Field(default='', max_length=200)
    activity: str = Field(default='', max_length=200)
    extra_question: str = Field(default='', max_length=1000)
    notes: str = Field(default='', max_length=1000)

    @field_validator('time')
    @classmethod
    def valid_time(cls, v):
        if v and int(v[:2]) > 23: raise ValueError('Horario inválido')
        return v

    @model_validator(mode='after')
    def validate_dates(self):
        if self.end_date and self.travel_date and self.end_date < self.travel_date:
            raise ValueError('La fecha final debe ser posterior a la inicial')
        if self.contact_confirmed and not self.phone:
            raise ValueError('Completar teléfono antes de confirmar destinatario')
        if self.date_confirmed and not self.travel_date:
            raise ValueError('Completar fecha antes de confirmarla')
        return self


NUMBERS = {'un':1, 'una':1, 'uno':1, 'dos':2, 'tres':3, 'cuatro':4, 'cinco':5,
           'seis':6, 'siete':7, 'ocho':8, 'nueve':9, 'diez':10, 'once':11, 'doce':12,
           'trece':13, 'catorce':14, 'quince':15, 'dieciseis':16, 'diecisiete':17,
           'dieciocho':18, 'diecinueve':19, 'veinte':20}
NUMBER = r'(\d{1,3}|' + '|'.join(NUMBERS) + r')'
DAYS = ['lunes','martes','miercoles','jueves','viernes','sabado','domingo']


def number(value): return int(value) if value.isdigit() else NUMBERS[value]


def extract(text, source_at, category='otro', name='', phone=''):
    t = normalized(text)
    local = source_at.astimezone(ZoneInfo('America/Argentina/Jujuy')).date()
    f = Ficha(category=category, name=name[:120], phone=phone)
    warnings = []
    totals = [number(m[0]) for m in re.findall(r'\b'+NUMBER+r'\s+(personas?|pasajeros?|pax)\b', t)]
    if not totals:
        totals = [number(m) for m in re.findall(r'\bsomos\s+'+NUMBER+r'\b',t)]
    adults = [number(m) for m in re.findall(r'\b'+NUMBER+r'\s+adultos?\b', t)]
    children = [number(m) for m in re.findall(r'\b'+NUMBER+r'\s+(?:ninos?|menores?)\b', t)]
    if not totals and len(adults)==1 and len(children)==1:
        totals = [adults[0]+children[0]]
    if len(totals)==1 and 1<=totals[0]<=500:
        f.passengers=totals[0]
    elif totals:
        warnings.append('Cantidad de pasajeros ambigua; revisar el mensaje.')

    explicit = list(re.finditer(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b', t))
    weekday = [d for d in DAYS if re.search(r'\b'+d+r'\b',t)]
    relative = list(re.finditer(r'\b(pasado manana|manana|hoy)\b',t))
    if len(explicit)==2 and re.search(r'\b(?:del|desde el)\s+\d{1,2}/\d{1,2}(?:/\d{4})?\s+(?:al|hasta el)\s+\d{1,2}/\d{1,2}',t):
        start,end=explicit
        f.date_text=(start.group()+' al '+end.group())[:200]
        try:
            first=date(int(start[3]) if start[3] else local.year,int(start[2]),int(start[1]))
            if not start[3] and first<local:first=date(local.year+1,first.month,first.day)
            last=date(int(end[3]) if end[3] else first.year,int(end[2]),int(end[1]))
            if not end[3] and last<first:last=date(first.year+1,last.month,last.day)
            if last<first:raise ValueError('Fechas invertidas')
            f.travel_date=first;f.end_date=last
        except ValueError:warnings.append('Rango de fechas inválido; revisar.')
    elif len(explicit)==1:
        m=explicit[0];f.date_text=m.group()
        try:
            proposed=date(int(m[3]) if m[3] else local.year,int(m[2]),int(m[1]))
            if not m[3] and proposed<local:
                proposed=date(local.year+1,int(m[2]),int(m[1]))
            f.travel_date=proposed
            if proposed<local:warnings.append('La fecha escrita es anterior al mensaje; confirmar.')
            if weekday and (len(weekday)>1 or DAYS[proposed.weekday()]!=weekday[0]):
                warnings.append('El día de la semana no coincide con la fecha escrita.')
        except ValueError:warnings.append('La fecha escrita no es válida.')
    elif not explicit and len(weekday)==1 and not relative:
        f.date_text=weekday[0]
        if re.search(r'\b(pasado|anterior|todos|cada)\b',t):
            warnings.append('Referencia semanal ambigua; completar fecha manualmente.')
        else:
            delta=(DAYS.index(weekday[0])-local.weekday())%7
            f.travel_date=local+timedelta(days=delta or 7)
    elif not explicit and not weekday and len(relative)==1:
        f.date_text=relative[0].group()
        # "por la mañana" denotes a time of day, not tomorrow.
        if f.date_text!='manana' or not re.search(r'\b(?:por|a) la manana\b',t):
            f.travel_date=local+timedelta(days={'hoy':0,'manana':1,'pasado manana':2}[f.date_text])
    elif explicit or weekday or relative:
        warnings.append('Se mencionan varias fechas; completar inicio y fin manualmente.')
    times=re.findall(r'\b(?:a las?|hora(?:rio)?\s*:?)[ ]*(\d{1,2}):(\d{2})\b',t)
    if len(times)==1 and int(times[0][0])<24 and int(times[0][1])<60:
        f.time=f'{int(times[0][0]):02d}:{times[0][1]}'
    flight=re.search(r'\bvuelo\s+([A-Za-z]{2}\s?\d{3,5})\b',text,re.I)
    if flight:f.flight=flight[1].upper()

    # Only explicit route clauses; retain original spelling. Stop at travel details.
    stop=r'(?=\s+(?:para|con|el|los|a las|mañana|manana|hoy|desde el día)\b|[.,;!?\n]|$)'
    route=re.search(r'\b(?:desde|(?:transfer|traslado)\s+(?:de|del))\s+(.+?)\s+(?:hasta|hacia|a)\s+(.+?)'+stop,text,re.I)
    if route:
        f.origin=route[1].strip()[:200];f.destination=route[2].strip()[:200]
    else:
        orig=re.search(r'\bdesde\s+(.+?)'+stop,text,re.I)
        dest=re.search(r'\b(?:hacia|hasta)\s+(.+?)'+stop,text,re.I)
        if orig:f.origin=orig[1].strip()[:200]
        if dest:f.destination=dest[1].strip()[:200]
    f.notes=' '.join(warnings)
    return f


def missing(f):
    result=[]
    def add(key,label,question):result.append({'field':key,'label':label,'question':question})
    if f.category=='otro':add('category','Servicio','¿Qué servicio necesitan?')
    if not f.passengers:add('passengers','Pasajeros','¿Cuántas personas viajan?')
    if not f.travel_date:add('travel_date','Fecha','¿Para qué fecha lo necesitan?')
    elif not f.date_confirmed:
        dates=f.travel_date.strftime('%d/%m/%Y')
        if f.end_date:dates+=' al '+f.end_date.strftime('%d/%m/%Y')
        add('date_confirmed','Confirmar fecha','¿Confirmás la fecha '+dates+'?')
    if f.category in ('transfer','traslado','alquiler_vehiculo'):
        if not f.origin.strip() or normalized(f.origin.strip()) in ('aeropuerto','el aeropuerto','un aeropuerto'):
            add('origin','Origen exacto','¿Desde qué aeropuerto o dirección salen?' if f.category=='transfer' else '¿Cuál es el punto de salida o retiro?')
        if not f.destination.strip():add('destination','Destino','¿Cuál es el destino o punto de devolución?')
        if not f.time and not f.flight:add('time','Horario o vuelo','¿Qué horario necesitan o cuál es el número de vuelo?' if f.category=='transfer' else '¿A qué hora lo necesitan?')
    if f.category in ('transfer','traslado') and not f.luggage.strip():
        add('luggage','Equipaje','¿Cuánto equipaje llevan?')
    if f.category in ('alojamiento_yala','alojamiento_carmen','alquiler_vehiculo') and not f.end_date:
        add('end_date','Fecha final','¿Hasta qué fecha lo necesitan?')
    if f.category in ('actividad','ticket','paquete') and not f.activity.strip():
        add('activity','Actividad','¿Qué actividad o recorrido les interesa?')
    return result


def draft_for(f):
    start='¡Hola! Somos Agencia ROMA.'
    if f.passengers:start+=f' Tomamos tu consulta para {f.passengers} personas.'
    questions=' '.join(item['question'] for item in missing(f))
    if f.extra_question.strip():questions+=' '+f.extra_question.strip()
    return (start+' '+(questions.strip() or 'Con estos datos revisaremos las opciones para preparar tu presupuesto.')+
            ' Disponibilidad y tarifa sujetas a confirmación.')
