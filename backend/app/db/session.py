from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def pin_utc(engine: Engine) -> Engine:
    """Every connection runs with TimeZone=UTC, whatever the server, database, role or client
    environment default is. psycopg returns timestamptz values in the session time zone, so on a
    non-UTC session the same instant would serialize as e.g. "...T12:00+02:00" when read back but
    "...T10:00Z" when freshly set in Python -- equal instants, unequal API strings.

    A SET on connect rather than a `-c timezone=UTC` startup option: libpq's PGTZ environment
    variable overrides that option, but not a SET issued after connecting. Committed so the setting
    survives the transaction it ran in."""

    @event.listens_for(engine, "connect")
    def _set_utc(dbapi_connection, _connection_record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
        dbapi_connection.commit()

    return engine


# Normal connection pool on a long-running backend — fixes prototype defect #10
# (docs/ARCHITECTURE.md §9, spec §14.10). No serverless-pool-of-1 workaround needed on Railway.
engine = pin_utc(create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
))

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
