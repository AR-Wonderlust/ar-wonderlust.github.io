"""Create local secrets once; never prints secrets and never overwrites them."""
import os
from pathlib import Path
import secrets

path=Path(__file__).with_name('.env.crm')
if path.exists():
    raise SystemExit('.env.crm ya existe. Se conserva sin modificar.')
data={
    'PGDATABASE':'roma_crm', 'PGUSER':'roma', 'PGPASSWORD':secrets.token_hex(32),
    'CRM_ADMIN_USER':'roma', 'CRM_ADMIN_PASSWORD':secrets.token_hex(24),
    'CRM_AUTOMATION_TOKEN':secrets.token_hex(32), 'CRM_BIND_IP':'127.0.0.1',
    'CRM_DRIVE_ORIGINAL_ID':'', 'CRM_EXTRACTION_MODEL':'', 'CATALOG_SOURCE':'drive',
}
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as file:
    file.write('# Privado: no publicar ni compartir. No regenerar PGPASSWORD con un volumen existente.\n')
    for key,value in data.items(): file.write(key+'='+value+'\n')
print('Creado .env.crm con permisos 600. Consultá el usuario y contraseña del panel localmente con nano .env.crm.')
