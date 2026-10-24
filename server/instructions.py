"""Load owner-edited text instructions; never execute skill files."""
import os
from pathlib import Path

MAX_FILES = 20
MAX_FILE_BYTES = 20000
MAX_TOTAL_BYTES = 80000


def load_instructions():
    root = Path(os.getenv('ASSISTANT_CONFIG_DIR', '/app/config'))
    if not root.exists():
        return ''
    if not root.is_dir():
        raise ValueError('La configuración debe ser una carpeta')
    root = root.resolve()
    files = []
    personality = root / 'personality.md'
    if personality.exists():
        files.append(personality)
    skills = root / 'skills'
    if skills.exists():
        if skills.is_symlink() or not skills.is_dir():
            raise ValueError('Carpeta de habilidades inválida')
        files.extend(sorted(skills.glob('*.md')))
        files.extend(sorted(skills.glob('*/SKILL.md')))
    if len(files) > MAX_FILES:
        raise ValueError('Demasiados archivos de instrucciones')
    parts = []
    total = 0
    for path in files:
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('Las instrucciones deben estar dentro de la carpeta configurada')
        with path.open('rb') as source:
            data = source.read(MAX_FILE_BYTES + 1)
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError('Instrucciones demasiado extensas')
        content = data.decode('utf-8').strip()
        if content:
            parts.append(f'INSTRUCCIÓN DEL OPERADOR: {path.relative_to(root)}\n{content}')
    return '\n\n'.join(parts)
