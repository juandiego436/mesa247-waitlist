"""Casos de uso del anfitrion. Todos detras del token de la tablet."""
from __future__ import annotations

from dataclasses import dataclass

from waitlist.application.errors import EntryNotFound, TableNotFound, VenueNotFound
from waitlist.application.ports.clock import Clock
from waitlist.application.ports.notifier import Notifier
from waitlist.domain.entities.table import Table, TableStatus
from waitlist.domain.entities.waitlist_entry import WaitlistStatus
from waitlist.domain.reports.daily_report import DailyReport
from waitlist.domain.services.queue_view import QueuePosition, build_queue_view
from waitlist.domain.services.seating_service import SeatingService
from waitlist.domain.value_objects.ids import EntryId, TableId, VenueId
from waitlist.domain.value_objects.service_date import ServiceDate


@dataclass(frozen=True, slots=True)
class HostBoard:
    venue_name: str
    service_date: ServiceDate
    queue: list[QueuePosition]
    tables: list[Table]
    average_wait_minutes: int | None


class _HostUseCase:
    def __init__(self, uow_factory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def _venue(self, uow, venue_id: str) -> tuple[VenueId, object]:
        vid = VenueId.parse(venue_id)
        venue = uow.venues.get(vid)
        if venue is None:
            raise VenueNotFound(f"Local desconocido: {venue_id}")
        return vid, venue


class ViewBoard(_HostUseCase):
    """La pantalla de la tablet: la cola y el estado real de las mesas."""

    def __init__(self, uow_factory, clock: Clock, minutes_per_party: int) -> None:
        super().__init__(uow_factory, clock)
        self._minutes_per_party = minutes_per_party

    def __call__(self, venue_id: str) -> HostBoard:
        now = self._clock.now()
        with self._uow_factory() as uow:
            vid, venue = self._venue(uow, venue_id)
            service_date = ServiceDate.for_venue(now, venue.timezone)
            entries = uow.waitlist.list_for_service_date(vid, service_date.value)
            mesas = uow.tables.list_for_venue(vid)

        cola = build_queue_view(entries, now, self._minutes_per_party)
        esperas = [
            e.waited_minutes(now)
            for e in entries
            if e.status is WaitlistStatus.SEATED
        ]
        return HostBoard(
            venue_name=venue.name,
            service_date=service_date,
            queue=cola,
            tables=mesas,
            average_wait_minutes=round(sum(esperas) / len(esperas)) if esperas else None,
        )


class CallForTable(_HostUseCase):
    """«Llamar». Retiene la mesa y avisa al comensal, en una transaccion."""

    def __init__(
        self, uow_factory, clock: Clock, seating: SeatingService, notifier: Notifier
    ) -> None:
        super().__init__(uow_factory, clock)
        self._seating = seating
        self._notifier = notifier

    def __call__(self, entry_id: str, table_id: str, force: bool = False) -> None:
        now = self._clock.now()
        with self._uow_factory() as uow:
            entry = uow.waitlist.get(EntryId.parse(entry_id))
            if entry is None:
                raise EntryNotFound(f"Entrada desconocida: {entry_id}")
            venue = uow.venues.get(entry.venue_id)

            # FOR UPDATE: aqui es donde dos tablets dejan de pisarse.
            mesa = uow.tables.get_for_update(TableId.parse(table_id))
            if mesa is None:
                raise TableNotFound(f"Mesa desconocida: {table_id}")
            anterior = (
                uow.tables.get_for_update(entry.assigned_table_id)
                if entry.assigned_table_id and entry.assigned_table_id != mesa.id
                else None
            )

            self._seating.call_for_table(entry, mesa, now, anterior, force)
            uow.commit()

        # Notificar DESPUES del commit y fuera de la transaccion: si el proveedor
        # tarda dos segundos, no queremos dos segundos de bloqueo sobre la fila
        # de la mesa. Y si falla, la mesa ya esta retenida correctamente.
        self._notifier.table_is_ready(entry, venue.name if venue else "")


class SeatParty(_HostUseCase):
    def __init__(self, uow_factory, clock: Clock, seating: SeatingService) -> None:
        super().__init__(uow_factory, clock)
        self._seating = seating

    def __call__(self, entry_id: str) -> None:
        now = self._clock.now()
        with self._uow_factory() as uow:
            entry = uow.waitlist.get(EntryId.parse(entry_id))
            if entry is None:
                raise EntryNotFound(f"Entrada desconocida: {entry_id}")
            mesa = (
                uow.tables.get_for_update(entry.assigned_table_id)
                if entry.assigned_table_id
                else None
            )
            self._seating.seat(entry, mesa, now)
            uow.commit()


class MarkNoShow(_HostUseCase):
    def __init__(self, uow_factory, clock: Clock, seating: SeatingService) -> None:
        super().__init__(uow_factory, clock)
        self._seating = seating

    def __call__(self, entry_id: str) -> None:
        now = self._clock.now()
        with self._uow_factory() as uow:
            entry = uow.waitlist.get(EntryId.parse(entry_id))
            if entry is None:
                raise EntryNotFound(f"Entrada desconocida: {entry_id}")
            mesa = (
                uow.tables.get_for_update(entry.assigned_table_id)
                if entry.assigned_table_id
                else None
            )
            self._seating.mark_no_show(entry, mesa, now)
            uow.commit()


class RemoveFromQueue(_HostUseCase):
    def __init__(self, uow_factory, clock: Clock, seating: SeatingService) -> None:
        super().__init__(uow_factory, clock)
        self._seating = seating

    def __call__(self, entry_id: str) -> None:
        now = self._clock.now()
        with self._uow_factory() as uow:
            entry = uow.waitlist.get(EntryId.parse(entry_id))
            if entry is None:
                raise EntryNotFound(f"Entrada desconocida: {entry_id}")
            mesa = (
                uow.tables.get_for_update(entry.assigned_table_id)
                if entry.assigned_table_id
                else None
            )
            self._seating.remove_by_host(entry, mesa, now)
            uow.commit()


class ReleaseTable(_HostUseCase):
    """«Mesa libre»: la pantalla que le falta al prototipo.

    Sin esto, a las nueve de la noche las veinte mesas estan marcadas como
    ocupadas, no hay ninguna que asignar y la tablet es un ladrillo. La
    auto-liberacion a los 75 minutos es la red por si el anfitrion se olvida
    -que un viernes se va a olvidar-, no el mecanismo principal.
    """

    def __call__(self, table_id: str) -> None:
        now = self._clock.now()
        with self._uow_factory() as uow:
            mesa = uow.tables.get_for_update(TableId.parse(table_id))
            if mesa is None:
                raise TableNotFound(f"Mesa desconocida: {table_id}")
            if mesa.status is TableStatus.HELD and mesa.held_by_entry_id:
                # Si alguien la tenia retenida, esa entrada tambien se cierra:
                # no puede quedar 'llamado' con una mesa que ya no es suya.
                entry = uow.waitlist.get(mesa.held_by_entry_id)
                if entry is not None and entry.is_active():
                    entry.release_table()
            mesa.release(now)
            uow.commit()


class BuildDailyReport(_HostUseCase):
    def __call__(self, venue_id: str, service_date: str | None = None) -> DailyReport:
        now = self._clock.now()
        with self._uow_factory() as uow:
            vid, venue = self._venue(uow, venue_id)
            jornada = (
                ServiceDate.parse(service_date)
                if service_date
                else ServiceDate.for_venue(now, venue.timezone)
            )
            entries = uow.waitlist.list_for_service_date(vid, jornada.value)

        # Con 142 filas por local y dia, calcular en memoria es correcto y se
        # testea sin base de datos. Deja de serlo cuando un local haga miles:
        # ahi se cambia por un GROUP BY en el adaptador y el dominio no se
        # entera. Decision reversible, no la pagamos hoy.
        return DailyReport.from_entries(vid, jornada, entries, now)
