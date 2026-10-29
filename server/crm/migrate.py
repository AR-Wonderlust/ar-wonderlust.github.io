"""Versioned, transactional migration runner with a PostgreSQL advisory lock."""
import asyncio
import hashlib
from pathlib import Path
from crm.db import connection


async def migrate():
    async with connection() as conn:
        await conn.execute('SELECT pg_advisory_xact_lock(19413001)')
        await conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())')
        for path in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
            sql = path.read_text()
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            row = await (await conn.execute('SELECT checksum FROM schema_migrations WHERE name=%s',(path.name,))).fetchone()
            if row:
                if row['checksum'] != checksum:
                    raise RuntimeError('Una migración aplicada fue modificada: '+path.name)
                continue
            await conn.execute(sql)
            await conn.execute('INSERT INTO schema_migrations(name,checksum) VALUES(%s,%s)',(path.name,checksum))
            print('Migración aplicada:',path.name)


if __name__ == '__main__':
    asyncio.run(migrate())
