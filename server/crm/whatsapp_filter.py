"""Local tourism intent filter: uncertainty stays reviewable, never silently deleted."""
import re
from crm.whatsapp_ficha import normalized


def classify_message(text):
    t=normalized(text)
    demand=bool(re.search(r'\b(busco|buscamos|necesito|necesitamos|quisiera|queremos|precio|cuanto\w*|donde|como llego|como llegar|alguien sabe|alguien conoce|alguien tiene|recomiendan|recomienda|consulta|looking for|need|procuro|preciso|tienen|alquilan)\b|有没有|需要',t))
    offer=bool(re.search(r'\b(ofrezco|ofrecemos|reservas al|tarifas promocionales|tenemos disponibilidad|promocion|aprovecha nuestra)\b',t))
    explicit_request=bool(re.search(r'\b(busco|buscamos|necesito|necesitamos|quisiera|alguien sabe|alguien conoce|donde|como llego|recomiendan)\b',t))
    category='otro';context=False
    if re.search(r'\b(transfer|aeropuerto|airport)\b',t): category='transfer';context=True
    elif re.search(r'\b(traslado\w*|transporte|taxi|remis|colectivo|omnibus|bus)\b',t):category='traslado';context=True
    elif re.search(r'\b(alojamiento|cabanas?|hospedaje|hotel\w*|hostel|hospedar\w*|alojar\w*|accommodation|lodging|apart)\b',t) or (re.search(r'\b(casa|departamento)\b',t) and re.search(r'\b(alquil\w*|vacacion\w*|noches?|temporario)\b',t)):
        context=True;category='alojamiento_yala' if 'yala' in t else 'alojamiento_carmen' if ('carmen' in t or 'cienaga' in t) else 'otro'
    elif re.search(r'\b(alquil\w*|rent\w*)\b',t) and re.search(r'\b(auto\w*|vehiculo\w*|mobi|camioneta\w*|van|car)\b',t):category='alquiler_vehiculo';context=True
    elif re.search(r'\b(excursion\w*|trekking|travesia|salinas|hornocal|tour\w*|hiking|paseo|enoturismo|termas|lagunas|visitar|turismo|viaje)\b',t):category='actividad';context=True
    elif re.search(r'\bcomo (?:llego|llegar) (?:a|al)\b',t) and re.search(r'\b(jujuy|salta|yala|purmamarca|tilcara|humahuaca|calilegua|carmen|cienaga|quebrada|puna|yungas)\b',t):category='traslado';context=True
    if context and category!='transfer' and re.search(r'\bcomo (?:llego|llegar) (?:a|al)\b',t):category='traslado'
    if offer and not explicit_request:return 'oferta',category
    if demand and context:
        if re.search(r'\bno (?:busco|necesito|queremos)\b',t):return 'revisar',category
        return 'posible_consulta',category
    if demand or context:return 'revisar',category
    return 'irrelevante',category
