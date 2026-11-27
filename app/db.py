import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./e5.db")
_es_sqlite = DATABASE_URL.startswith("sqlite")
_url = make_url(DATABASE_URL)
_db_file = _url.database if _es_sqlite else None
DATABASE_PATH = (
    Path(_db_file).resolve()
    if _db_file and _db_file != ":memory:"
    else Path.cwd() / "e5.db"
)

if _db_file and _db_file != ":memory:":
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _es_sqlite else {},
)


if _es_sqlite:
    @event.listens_for(engine, "connect")
    def _configurar_sqlite(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA wal_autocheckpoint=1000")
        cursor.execute("PRAGMA journal_size_limit=8388608")
        cursor.close()


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def crear_tablas() -> None:
    from app import models

    Base.metadata.create_all(bind=engine)
