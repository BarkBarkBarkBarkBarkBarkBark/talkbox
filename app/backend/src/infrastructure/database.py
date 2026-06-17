import psycopg

from src.infrastructure.config import settings
from src.infrastructure.db import to_sync_dsn


def get_db_connection():
    return psycopg.connect(to_sync_dsn(settings.db_uri))
