from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from waitlist.domain.errors import InvalidTransition
from waitlist.domain.value_objects.guest_name import GuestName
from waitlist.domain.value_objects.ids import EntryId, TableId, VenueId
from waitlist.domain.value_objects.party_size import PartySize
from waitlist.domain.value_objects.phone_number import PhoneNumber
from waitlist.domain.value_objects.public_token import PublicToken
from waitlist.domain.value_objects.service_date import ServiceDate


class WaitlistStatus(Enum):
    WAITING = "waiting"
    CALLED = "called"
    SEATED = "seated"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class CancelledBy(Enum):
    GUEST = "guest"
    HOST = "host"


_ACTIVE = frozenset({WaitlistStatus.WAITING, WaitlistStatus.CALLED})
_TERMINAL = frozenset(
    {WaitlistStatus.SEATED, WaitlistStatus.CANCELLED, WaitlistStatus.NO_SHOW}
)


@dataclass
class WaitlistEntry:
    """Un grupo esperando mesa en un local, en una jornada.

    Sin decoradores de ORM y sin imports de fuera del dominio: esta clase se
    puede instanciar, recorrer entera y testear sin MySQL delante.

    Lo que NO guarda, a proposito:
      - la posicion en la cola: depende de quien este delante, o sea de la cola
        entera. Guardarla obliga a reescribir 40 filas cada vez que alguien se
        sienta, con dos anfitriones tocando la tablet a la vez. Se calcula.
      - el tiempo estimado: funcion del ritmo del local, no de esta entrada.
      - la etiqueta 'Frecuente': ese dato vive en El Libro.
    """

    id: EntryId
    venue_id: VenueId
    service_date: ServiceDate
    guest_name: GuestName
    phone: PhoneNumber
    party_size: PartySize
    public_token: PublicToken
    joined_at: datetime
    status: WaitlistStatus = WaitlistStatus.WAITING
    called_at: datetime | None = None
    on_the_way_at: datetime | None = None
    hold_expires_at: datetime | None = None
    call_count: int = 0
    closed_at: datetime | None = None
    cancelled_by: CancelledBy | None = None
    assigned_table_id: TableId | None = None
    table_assigned_at: datetime | None = None
    seated_over_capacity: bool = False
    # Lo que le PROMETIMOS al unirse. No se puede reconstruir despues, y es lo
    # unico que permite comparar prometido contra real en el reporte.
    quoted_wait_minutes: int | None = None
    version: int = 0

    # --- creacion --------------------------------------------------------

    @classmethod
    def join(
        cls,
        *,
        venue_id: VenueId,
        service_date: ServiceDate,
        guest_name: GuestName,
        phone: PhoneNumber,
        party_size: PartySize,
        now: datetime,
        quoted_wait_minutes: int | None = None,
    ) -> "WaitlistEntry":
        return cls(
            id=EntryId.new(),
            venue_id=venue_id,
            service_date=service_date,
            guest_name=guest_name,
            phone=phone,
            party_size=party_size,
            public_token=PublicToken.new(),
            joined_at=now,
            quoted_wait_minutes=quoted_wait_minutes,
        )

    # --- consultas -------------------------------------------------------

    def is_active(self) -> bool:
        return self.status in _ACTIVE

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL

    def is_holding_a_table(self) -> bool:
        return self.status is WaitlistStatus.CALLED and self.assigned_table_id is not None

    def hold_has_expired(self, now: datetime) -> bool:
        """Consulta, no transicion. Nadie pasa a NO_SHOW solo: que se venza la
        ventana de 10 minutos es informacion para el anfitrion, que es quien
        ve si la persona esta en la puerta. Asi no hace falta un scheduler."""
        if self.status is not WaitlistStatus.CALLED or self.hold_expires_at is None:
            return False
        return now >= self.hold_expires_at

    def waited_minutes(self, now: datetime) -> int:
        end = self.closed_at or now
        return max(0, int((end - self.joined_at).total_seconds() // 60))

    # --- transiciones ----------------------------------------------------

    def call_for_table(
        self,
        *,
        table_id: TableId,
        now: datetime,
        hold_window: timedelta,
        over_capacity: bool = False,
    ) -> None:
        """Llamar y asignar mesa son un solo acto.

        En el salon real tambien lo son: se desocupa la 7, miras quien entra en
        la 7, la llamas. Llamar a alguien sin tener donde sentarlo es el
        problema que esto viene a resolver.

        Se puede volver a llamar (a la misma mesa o a otra): reinicia la ventana
        y suma a call_count. Lo que no se puede es llamar a alguien ya sentado,
        cancelado o marcado como no-show.
        """
        self.ensure_active("llamar")
        self.status = WaitlistStatus.CALLED
        self.assigned_table_id = table_id
        self.table_assigned_at = now
        self.called_at = self.called_at or now
        self.hold_expires_at = now + hold_window
        self.call_count += 1
        self.seated_over_capacity = over_capacity
        self.on_the_way_at = None

    def confirm_on_the_way(self, now: datetime) -> None:
        """'Voy en camino' no es un estado nuevo: no cambia lo que el anfitrion
        puede hacer despues (sentar o marcar no-show). Es una marca de tiempo,
        y ahorra las cuatro transiciones que un estado propio arrastraria."""
        if self.status is not WaitlistStatus.CALLED:
            raise InvalidTransition(
                f"Solo se confirma tras ser llamado (estado actual: {self.status.value})"
            )
        self.on_the_way_at = now

    def seat(self, now: datetime) -> None:
        self.ensure_active("sentar")
        self.status = WaitlistStatus.SEATED
        self.closed_at = now
        self.hold_expires_at = None

    def cancel_by_guest(self, now: datetime) -> None:
        self.ensure_active("cancelar")
        self._close(WaitlistStatus.CANCELLED, now, CancelledBy.GUEST)

    def remove_by_host(self, now: datetime) -> None:
        self.ensure_active("retirar de la cola")
        self._close(WaitlistStatus.CANCELLED, now, CancelledBy.HOST)

    def mark_no_show(self, now: datetime) -> None:
        if self.status is not WaitlistStatus.CALLED:
            raise InvalidTransition(
                "Solo se marca no-show a quien fue llamado "
                f"(estado actual: {self.status.value})"
            )
        self._close(WaitlistStatus.NO_SHOW, now, None)

    def release_table(self) -> TableId | None:
        """Suelta la mesa y devuelve cual era, para que el servicio de dominio
        la libere. Es una operacion interna: el caso de uso no deberia tener que
        acordarse de llamarla, por eso SeatingService la encadena a cada
        transicion terminal. Si depende de la memoria del desarrollador, un dia
        una mesa se queda retenida por alguien que se fue hace dos horas."""
        table_id, self.assigned_table_id = self.assigned_table_id, None
        self.table_assigned_at = None
        self.hold_expires_at = None
        return table_id

    # --- guardas ---------------------------------------------------------

    def _close(
        self, status: WaitlistStatus, now: datetime, by: CancelledBy | None
    ) -> None:
        self.status = status
        self.closed_at = now
        self.cancelled_by = by
        self.hold_expires_at = None

    def ensure_active(self, action: str) -> None:
        """Publica porque SeatingService la necesita: antes de retener una mesa
        hay que saber que la entrada admite la transicion, o retendriamos una
        mesa que despues habria que devolver."""
        if not self.is_active():
            raise InvalidTransition(
                f"No se puede {action}: la entrada ya esta {self.status.value}"
            )
