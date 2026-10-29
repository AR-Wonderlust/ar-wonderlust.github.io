"""Read-only deployment check; prints no credentials, contacts, or conversations."""
import asyncio
from crm.db import connection


async def main():
    async with connection() as conn:
        for table in ['schema_migrations','categories','enquiries','catalog_items','automation_events']:
            # Fixed allowlist above, not user input.
            row=await (await conn.execute('SELECT count(*) AS total FROM '+table)).fetchone()
            print(table+':',row['total'])
    print('POSTGRESQL: OK. Para probar captura y panel, seguir docs/CRM-ROMA.md.')


if __name__=='__main__':
    asyncio.run(main())
