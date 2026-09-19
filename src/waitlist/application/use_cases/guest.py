"""Casos de uso del comensal. Todos detras del QR, ninguno con login."""
from __future__ import annotations

from dataclasses import dataclass

from waitlist.application.errors import AlreadyInQueue, EntryNotFound, VenueNotFound
from waitlist.application.ports.clock import Clock
from waitlist.domain.entities.waitlist_entry import WaitlistEntry
from waitlist.domain.services.queue_view import (
    build_queue_view,
    estimate_wait_for_newcomer,
)
from waitlist.domain.services.seating_service import SeatingService
from waitlist.domain.value_objects.guest_name import GuestName
from waitlist.domain.value_objects.ids import VenueId
from waitlist.domain.value_objects.party_size import PartySize
from waitlist.domain.value_objects.phone_number import PhoneNumber
from waitlist.domain.value_objects.service_date import ServiceDate


@dataclass(frozen=True, slots=True)
class GuestView:
    entry: WaitlistEntry
    venue_name: str
    position: int | None
    estimated_wait_minutes: int | None
    ahead: int


class JoinQueue:
    def __init__(self, uow_factory, clock: Clock, minutes_per_party: int) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._minutes_per_party = minutes_per_party

    def __call__(
        self, venue_id: str, name: str, phone: str, party_size: int
    ) -> GuestView:
        now = self._clock.now()
        with self._uow_factory() as uow:
            vid = VenueId.parse(venue_id)
            venue = uow.venues.get(vid)
            if venue is None:
                raise VenueNotFound(f"Local desconocido: {venue_id}")

            # El pais sale del local, no del formulario: un comensal de Lima que
            # escanea el QR de Casa Mediterranea escribe su movil peruano y el
            # de Santiago el suyo. Los dos tienen que entrar.
            telefono = PhoneNumber.parse(phone, venue.country)
            if uow.waitlist.has_active_phone(vid, telefono.e164):
                existente = self._buscar_activa(uow, vid, telefono.e164, now, venue)
                raise AlreadyInQueue(existente)

            service_date = ServiceDate.for_venue(now, venue.timezone)
            cola = uow.waitlist.list_for_service_date(vid, service_date.value)

            entry = WaitlistEntry.join(
                venue_id=vid,
                service_date=service_date,
                guest_name=GuestName.parse(name),
                phone=telefono,
                party_size=PartySize.parse(party_size),
                now=now,
                quoted_wait_minutes=estimate_wait_for_newcomer(
                    cola, self._minutes_per_party
                ),
            )
            uow.waitlist.add(entry)
            uow.commit()

        posicion = len([e for e in cola if e.is_active()]) + 1
        return GuestView(
            entry=entry,
            venue_name=venue.name,
            position=posicion,
            estimated_wait_minutes=entry.quoted_wait_minutes,
            ahead=posicion - 1,
        )

    def _buscar_activa(self, uow, vid, e164, now, venue) -> str:
        service_date = ServiceDate.for_venue(now, venue.timezone)
        for e in uow.waitlist.list_for_service_date(vid, service_date.value):
            if e.is_active() and e.phone.e164 == e164:
                return e.public_token.value
        return ""


class ViewMyPlace:
    """Lo que el comensal consulta cada pocos segundos desde la puerta.

    Es el endpoint mas llamado del sistema y el unico completamente publico.
    Devuelve SOLO la entrada de quien trae el token: ni un nombre ni un telefono
    de nadie mas.
    """

    def __init__(self, uow_factory, clock: Clock, minutes_per_party: int) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._minutes_per_party = minutes_per_party

    def __call__(self, token: str) -> GuestView:
        now = self._clock.now()
        with self._uow_factory() as uow:
            entry = uow.waitlist.get_by_token(token)
            if entry is None:
                raise EntryNotFound("No encontramos tu puesto en la cola")
            venue = uow.venues.get(entry.venue_id)
            cola = uow.waitlist.list_for_service_date(
                entry.venue_id, entry.service_date.value
            )

        vista = build_queue_view(cola, now, self._minutes_per_party)
        mio = next((v for v in vista if v.entry.id == entry.id), None)
        return GuestView(
            entry=entry,
            venue_name=venue.name if venue else "",
            position=mio.position if mio else None,
            estimated_wait_minutes=mio.estimated_wait_minutes if mio else None,
            ahead=(mio.position - 1) if mio else 0,
        )


class ConfirmOnTheWay:
    def __init__(self, uow_factory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def __call__(self, token: str) -> None:
        with self._uow_factory() as uow:
            entry = uow.waitlist.get_by_token(token)
            if entry is None:
                raise EntryNotFound("No encontramos tu puesto en la cola")
            entry.confirm_on_the_way(self._clock.now())
            uow.commit()


class CancelMyPlace:
    """«Ya no voy». Libera la mesa si ya se la habian retenido."""

    def __init__(self, uow_factory, clock: Clock, seating: SeatingService) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._seating = seating

    def __call__(self, token: str) -> None:
        now = self._clock.now()
        with self._uow_factory() as uow:
            entry = uow.waitlist.get_by_token(token)
            if entry is None:
                raise EntryNotFound("No encontramos tu puesto en la cola")
            mesa = (
                uow.tables.get_for_update(entry.assigned_table_id)
                if entry.assigned_table_id
                else None
            )
            self._seating.cancel_by_guest(entry, mesa, now)
            uow.commit()
