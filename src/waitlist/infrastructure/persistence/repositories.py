from __future__ import annotations

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from waitlist.application.ports.venues import VenueProfile, VenueReader
from waitlist.domain.entities.table import Table
from waitlist.domain.entities.waitlist_entry import WaitlistEntry
from waitlist.domain.value_objects.ids import EntryId, TableId, VenueId
from waitlist.infrastructure.persistence import schema
from waitlist.infrastructure.persistence.mappers import (
    entry_to_row,
    row_to_entry,
    row_to_table,
    table_to_row,
)

_ACTIVE = ("waiting", "called")


class SqlWaitlistRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self._nuevos: dict[str, WaitlistEntry] = {}
        self._vistos: dict[str, WaitlistEntry] = {}

    # --- escritura ---

    def add(self, entry: WaitlistEntry) -> None:
        self._nuevos[str(entry.id)] = entry

    def flush(self) -> None:
        """Escribe al cerrar la transaccion, no en cada mutacion.

        Las entidades se cargan, se mutan en memoria y se vuelcan aqui. Asi el
        caso de uso no tiene que acordarse de llamar a save() despues de cada
        transicion, que es exactamente el tipo de cosa que un dia se olvida.
        """
        for entry in self._nuevos.values():
            self._conn.execute(schema.waitlist_entries.insert().values(entry_to_row(entry)))
        for entry in self._vistos.values():
            if str(entry.id) in self._nuevos:
                continue
            row = entry_to_row(entry)
            row["version"] = entry.version + 1
            self._conn.execute(
                schema.waitlist_entries.update()
                .where(schema.waitlist_entries.c.id == str(entry.id))
                .values(row)
            )
        self._nuevos.clear()
        self._vistos.clear()

    # --- lectura ---

    def get(self, entry_id: EntryId) -> WaitlistEntry | None:
        return self._one(schema.waitlist_entries.c.id == str(entry_id))

    def get_by_token(self, token: str) -> WaitlistEntry | None:
        return self._one(schema.waitlist_entries.c.public_token == token)

    def list_for_service_date(
        self, venue_id: VenueId, service_date: date
    ) -> list[WaitlistEntry]:
        rows = self._conn.execute(
            select(schema.waitlist_entries)
            .where(schema.waitlist_entries.c.venue_id == str(venue_id))
            .where(schema.waitlist_entries.c.service_date == service_date)
            .order_by(schema.waitlist_entries.c.joined_at)
        ).mappings()
        return [self._track(row_to_entry(r)) for r in rows]

    def has_active_phone(self, venue_id: VenueId, phone_e164: str) -> bool:
        """Un mismo movil no puede tener dos entradas vivas en el mismo local.

        El QR de la puerta no tiene login: sin esto, cinco toques nerviosos en
        'Unirme' son cinco personas en la cola del anfitrion.
        """
        found = self._conn.execute(
            select(schema.waitlist_entries.c.id)
            .where(schema.waitlist_entries.c.venue_id == str(venue_id))
            .where(schema.waitlist_entries.c.phone_e164 == phone_e164)
            .where(schema.waitlist_entries.c.status.in_(_ACTIVE))
            .limit(1)
        ).first()
        return found is not None

    def _one(self, condition) -> WaitlistEntry | None:
        row = self._conn.execute(
            select(schema.waitlist_entries).where(condition)
        ).mappings().first()
        return self._track(row_to_entry(row)) if row else None

    def _track(self, entry: WaitlistEntry) -> WaitlistEntry:
        # Devolver siempre la misma instancia por id: si un caso de uso carga la
        # cola y ademas la entrada por id, las dos mutaciones tienen que caer en
        # el mismo objeto o una se pierde al volcar.
        key = str(entry.id)
        if key in self._vistos:
            return self._vistos[key]
        self._vistos[key] = entry
        return entry


class SqlTableRepository:
    def __init__(self, conn: Connection, use_row_locks: bool) -> None:
        self._conn = conn
        self._use_row_locks = use_row_locks
        self._vistas: dict[str, Table] = {}

    def get(self, table_id: TableId) -> Table | None:
        return self._one(table_id, lock=False)

    def get_for_update(self, table_id: TableId) -> Table | None:
        """SELECT ... FOR UPDATE: el guardia real contra el doble-booking.

        Sin el, dos anfitriones leen la mesa como libre en el mismo milisegundo,
        los dos escriben, y gana el ultimo: uno de los dos cree tener una mesa
        que no tiene, y a las nueve de la noche hay dos grupos de pie delante de
        la misma mesa.

        SQLite no tiene FOR UPDATE y no lo necesita: serializa las escrituras.
        Por eso el bloqueo depende del perfil, y por eso el test que de verdad
        prueba esto tiene que correr contra MySQL.
        """
        return self._one(table_id, lock=self._use_row_locks)

    def list_for_venue(self, venue_id: VenueId) -> list[Table]:
        rows = self._conn.execute(
            select(schema.tables)
            .where(schema.tables.c.venue_id == str(venue_id))
            .order_by(schema.tables.c.seats, schema.tables.c.label)
        ).mappings()
        return [self._track(row_to_table(r)) for r in rows]

    def flush(self) -> None:
        for table in self._vistas.values():
            row = table_to_row(table)
            row["version"] = table.version + 1
            self._conn.execute(
                update(schema.tables)
                .where(schema.tables.c.id == str(table.id))
                .values(row)
            )
        self._vistas.clear()

    def _one(self, table_id: TableId, lock: bool) -> Table | None:
        stmt = select(schema.tables).where(schema.tables.c.id == str(table_id))
        if lock:
            stmt = stmt.with_for_update()
        row = self._conn.execute(stmt).mappings().first()
        return self._track(row_to_table(row)) if row else None

    def _track(self, table: Table) -> Table:
        key = str(table.id)
        if key in self._vistas:
            return self._vistas[key]
        self._vistas[key] = table
        return table


class SqlVenueReader(VenueReader):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get(self, venue_id: VenueId) -> VenueProfile | None:
        row = self._conn.execute(
            select(schema.venues).where(schema.venues.c.id == str(venue_id))
        ).mappings().first()
        return self._to_profile(row) if row else None

    def list_all(self) -> list[VenueProfile]:
        rows = self._conn.execute(
            select(schema.venues).order_by(schema.venues.c.name)
        ).mappings()
        return [self._to_profile(r) for r in rows]

    @staticmethod
    def _to_profile(row) -> VenueProfile:
        return VenueProfile(
            id=VenueId.parse(row["id"]),
            name=row["name"],
            timezone=row["timezone"],
            country=row["country"],
            expected_turn_minutes=row["expected_turn_minutes"],
        )
