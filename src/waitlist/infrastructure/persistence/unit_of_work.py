from __future__ import annotations

from sqlalchemy import Engine

from waitlist.infrastructure.persistence.repositories import (
    SqlTableRepository,
    SqlVenueReader,
    SqlWaitlistRepository,
)


class SqlAlchemyUnitOfWork:
    """Una transaccion por caso de uso.

    Llamar a un comensal toca dos agregados -la entrada y la mesa- y o se
    guardan los dos o ninguno. Si solo se guardara la mesa, quedaria retenida
    para una entrada que nunca fue llamada, y esa mesa no vuelve a estar libre
    hasta que caduque sola.
    """

    def __init__(self, engine: Engine, use_row_locks: bool) -> None:
        self._engine = engine
        self._use_row_locks = use_row_locks
        self._conn = None
        self._tx = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self._conn = self._engine.connect()
        self._tx = self._conn.begin()
        self.waitlist = SqlWaitlistRepository(self._conn)
        self.tables = SqlTableRepository(self._conn, self._use_row_locks)
        self.venues = SqlVenueReader(self._conn)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            if self._conn is not None:
                self._conn.close()
            self._conn = None
            self._tx = None

    def commit(self) -> None:
        # Volcar primero: las entidades se mutaron en memoria y hasta aqui no ha
        # salido ni un UPDATE.
        self.waitlist.flush()
        self.tables.flush()
        self._tx.commit()

    def rollback(self) -> None:
        if self._tx is not None and self._tx.is_active:
            self._tx.rollback()


def unit_of_work_factory(engine: Engine, is_sqlite: bool):
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(engine, use_row_locks=not is_sqlite)

    return factory
