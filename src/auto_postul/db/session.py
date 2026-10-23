"""Motor SQLite, sesiones y transacciones."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from auto_postul.config import Settings, get_settings
from auto_postul.db import models as _models  # noqa: F401  (registra los modelos)
from auto_postul.db.base import Base

_ENGINES: dict[str, Engine] = {}
_FACTORIES: dict[str, sessionmaker[Session]] = {}


def get_engine(settings: Settings | None = None) -> Engine:
    """Crea o reutiliza el engine por URL y activa garantías de SQLite."""
    current = settings or get_settings()
    key = current.database_url
    cached = _ENGINES.get(key)
    if cached is not None:
        return cached
    engine = create_engine(
        key,
        connect_args={"check_same_thread": False, "timeout": 10},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    _ENGINES[key] = engine
    return engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    current = settings or get_settings()
    key = current.database_url
    cached = _FACTORIES.get(key)
    if cached is not None:
        return cached
    factory = sessionmaker(bind=get_engine(current), expire_on_commit=False)
    _FACTORIES[key] = factory
    return factory


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Transacción explícita: commit al salir bien, rollback ante error."""
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(settings: Settings | None = None) -> None:
    """Crea tablas faltantes. Alembic sigue siendo la fuente de migraciones."""
    Base.metadata.create_all(get_engine(settings))
