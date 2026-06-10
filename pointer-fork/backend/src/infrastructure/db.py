"""Database-URL helpers shared by every module that talks to Postgres."""


def to_sync_dsn(db_uri: str) -> str:
    """Strip SQLAlchemy driver prefixes so psycopg2 / psycopg can consume the URL.

    pydantic-settings stores DB_URI in the SQLAlchemy-flavoured form
    ``postgresql+psycopg://user:pass@host:port/db``. psycopg2 rejects that with
    ``invalid dsn: missing "=" after "postgresql+psycopg://..."``.
    """
    return (
        db_uri.replace("postgresql+psycopg://", "postgresql://")
              .replace("postgresql+psycopg2://", "postgresql://")
              .replace("postgresql+asyncpg://", "postgresql://")
              .replace("postgresql+psycopg_async://", "postgresql://")
    )
