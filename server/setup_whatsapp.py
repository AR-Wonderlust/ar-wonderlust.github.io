"""Generate local connector secrets without overwriting existing keys."""
import os
from pathlib import Path
import secrets
path=Path(__file__).resolve().with_name('.env.whatsapp')
try:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
except FileExistsError:
    print('.env.whatsapp ya existe. Se conserva sin modificar.')
else:
    with os.fdopen(fd,'w') as f:
        f.write('WA_BRIDGE_TOKEN='+secrets.token_hex(32)+'\nWA_SESSION_KEY='+secrets.token_hex(32)+'\n')
    print('.env.whatsapp creado con permisos 600. No compartir ni regenerar la clave de sesiones.')
