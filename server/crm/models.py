from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

Category = Literal['transfer','traslado','alojamiento_yala','alojamiento_carmen','alquiler_vehiculo','actividad','ticket','paquete','otro']


class EnquiryInput(BaseModel):
    request_id: UUID
    summary: str = Field(min_length=1,max_length=6000)
    categories: list[Category] = Field(default_factory=lambda:['otro'],min_length=1,max_length=9)
    name: str = Field(default='',max_length=120)
    contact: str = Field(default='',max_length=250)
    travel_start: date | None = None
    travel_end: date | None = None
    passengers: int | None = Field(default=None,ge=1,le=500)
    consent: Literal[True]

    @model_validator(mode='after')
    def validate_dates(self):
        if not self.summary.strip():
            raise ValueError('La consulta no puede estar vacía')
        if self.travel_start and self.travel_end and self.travel_end < self.travel_start:
            raise ValueError('La salida no puede ser anterior a la llegada')
        return self


class EnquiryUpdate(BaseModel):
    version: int = Field(ge=1)
    status: Literal['nueva','contactada','presupuestada','aceptada','perdida','cerrada']
    owner: str = Field(default='',max_length=120)
    next_action: str = Field(default='',max_length=500)
    follow_up_at: datetime | None = None
    loss_reason: str = Field(default='',max_length=500)
    categories: list[Category] = Field(min_length=1,max_length=9)
    name: str = Field(default='',max_length=120)
    contact: str = Field(default='',max_length=250)

    @model_validator(mode='after')
    def validate_loss(self):
        if self.status == 'perdida' and not self.loss_reason.strip():
            raise ValueError('Indicar motivo de pérdida')
        if self.follow_up_at and self.follow_up_at.tzinfo is None:
            raise ValueError('Usar fecha y hora con zona horaria')
        return self


class CatalogInput(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    category_code: Category = 'actividad'
    content: str = Field(min_length=1,max_length=20000)
    starts_on: date | None = None
    ends_on: date | None = None
    permanent: bool = False
    source_url: str = Field(default='',max_length=500)

    @model_validator(mode='after')
    def validate_dates(self):
        if not self.title.strip() or not self.content.strip():
            raise ValueError('Completar título y contenido')
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError('Fechas invertidas')
        if self.source_url and not self.source_url.startswith('https://'):
            raise ValueError('La fuente debe usar HTTPS')
        return self


class CatalogUpdate(CatalogInput):
    version: int = Field(ge=1)
    status: Literal['pendiente','aprobado','archivado'] = 'pendiente'

    @model_validator(mode='after')
    def validate_approval(self):
        if self.status == 'aprobado' and not self.permanent and not (self.starts_on and self.ends_on):
            raise ValueError('Para aprobar: indicar ambas fechas con año o marcar permanente')
        return self
