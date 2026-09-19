from __future__ import annotations

from datetime import date
from typing import Protocol

from waitlist.domain.entities.table import Table
from waitlist.domain.entities.waitlist_entry import WaitlistEntry
from waitlist.domain.value_objects.ids import EntryId, TableId, VenueId


class WaitlistRepository(Protocol):
    def add(self, entry: WaitlistEntry) -> None: ...
    def get(self, entry_id: EntryId) -> WaitlistEntry | None: ...
    def get_by_token(self, token: str) -> WaitlistEntry | None: ...
    def list_for_service_date(
        self, venue_id: VenueId, service_date: date
    ) -> list[WaitlistEntry]: ...
    def has_active_phone(self, venue_id: VenueId, phone_e164: str) -> bool: ...


class TableRepository(Protocol):
    def get(self, table_id: TableId) -> Table | None: ...
    def get_for_update(self, table_id: TableId) -> Table | None:
        """Lee la mesa bloqueando su fila hasta el fin de la transaccion.

        Este es el guardia real contra el doble-booking. Sin el, dos anfitriones
        leen la mesa como libre en el mismo milisegundo, los dos escriben, y
        gana el ultimo: uno de los dos cree tener una mesa que no tiene.

        Ojo: NO es un indice unico parcial. MySQL no los tiene, eso es Postgres.
        """
        ...

    def list_for_venue(self, venue_id: VenueId) -> list[Table]: ...


class UnitOfWork(Protocol):
    """Una transaccion por caso de uso.

    Llamar toca dos agregados -la entrada y la mesa- y o se guardan los dos o
    ninguno. Si se guardara solo la mesa, quedaria retenida para una entrada que
    nunca fue llamada.
    """

    waitlist: WaitlistRepository
    tables: TableRepository

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, *exc) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
