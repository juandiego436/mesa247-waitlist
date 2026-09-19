from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

from waitlist.infrastructure.config.settings import Settings, get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return build_engine(get_settings())


def build_engine(settings: Settings, url: str | None = None) -> Engine:
    url = url or settings.database_url

    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            echo=settings.db_echo,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if ":memory:" in url else None,
        )
        _enable_sqlite_foreign_keys(engine)
        return engine

    return create_engine(
        url,
        echo=settings.db_echo,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_size,
        pool_pre_ping=True,
        # Cloud SQL corta las conexiones ociosas. Sin recycle, la primera
        # peticion despues de un rato tranquilo falla con "server has gone
        # away", que en un restaurante es a las 18:30 justo antes del turno.
        pool_recycle=settings.db_pool_recycle_seconds,
    )


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignora las claves foraneas salvo que se pidan por conexion.

    Sin esto, el perfil local acepta datos que MySQL rechazaria, y el error
    aparece en staging en vez de en el portatil.
    """

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
