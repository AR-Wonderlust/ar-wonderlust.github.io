import os
from contextlib import asynccontextmanager
import psycopg
from psycopg.rows import dict_row


def enabled():
    return os.getenv('CRM_ENABLED', 'false').lower() == 'true'


@asynccontextmanager
async def connection():
    # libpq reads PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD from the environment.
    # Connections close after each short transaction; no pool retained between CLI runs.
    async with await psycopg.AsyncConnection.connect(
        connect_timeout=5, row_factory=dict_row,
        options='-c statement_timeout=5000 -c lock_timeout=3000',
    ) as conn:
        yield conn
