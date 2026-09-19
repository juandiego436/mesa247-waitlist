from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from waitlist.domain.errors import InvalidValue, TableNotAvailable
from waitlist.domain.value_objects.ids import EntryId, TableId, VenueId
from waitlist.domain.value_objects.party_size import PartySize

# Colchon sobre la ventana de 10 minutos del comensal: si el anfitrion ni
# sienta ni marca no-show, la retencion no puede bloquear la mesa para siempre.
HOLD_GRACE = timedelta(minutes=5)


class TableStatus(Enum):
    AVAILABLE = "available"
    HELD = "held"
    OCCUPIED = "occupied"


@dataclass
class Table:
    """Una mesa del local, como recurso asignable.

    El catalogo (cuantas mesas hay y de cuantas plazas) es de El Libro; nosotros
    no inventamos mesas. Lo que si es nuestro es quien la tiene retenida ahora
    mismo por un walk-in. 'external_ref' es el hilo hacia El Libro y es nulable
    a proposito, para que el piloto corra sin esa integracion.
    """

    id: TableId
    venue_id: VenueId
    label: str
    seats: int
    status: TableStatus = TableStatus.AVAILABLE
    held_by_entry_id: EntryId | None = None
    held_at: datetime | None = None
    occupied_since: datetime | None = None
    auto_release_at: datetime | None = None
    external_ref: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        if self.seats < 1:
            raise InvalidValue(f"Una mesa tiene al menos 1 plaza: {self.seats}")
        if not str(self.label).strip():
            raise InvalidValue("La mesa necesita una etiqueta visible")

    # --- consultas -------------------------------------------------------

    def can_fit(self, party_size: PartySize) -> bool:
        return int(party_size) <= self.seats

    def effective_status(self, now: datetime) -> TableStatus:
        """El estado que ve el anfitrion, con la caducidad ya aplicada.

        La liberacion automatica se CALCULA al leer, no se escribe con un
        trabajo programado. Nos ahorra un worker y un cron en Cloud Run, que
        escala a cero y no tiene donde alojar un proceso residente.
        """
        if self.status is TableStatus.AVAILABLE:
            return TableStatus.AVAILABLE
        if self.auto_release_at is not None and now >= self.auto_release_at:
            return TableStatus.AVAILABLE
        return self.status

    def is_available_at(self, now: datetime) -> bool:
        return self.effective_status(now) is TableStatus.AVAILABLE

    # --- transiciones ----------------------------------------------------

    def hold_for(
        self, entry_id: EntryId, now: datetime, hold_window: timedelta
    ) -> None:
        self._apply_expiry(now)
        if self.status is not TableStatus.AVAILABLE:
            raise TableNotAvailable(
                f"La mesa {self.label} esta {self.status.value}"
            )
        self.status = TableStatus.HELD
        self.held_by_entry_id = entry_id
        self.held_at = now
        self.occupied_since = None
        self.auto_release_at = now + hold_window + HOLD_GRACE

    def occupy(self, now: datetime, expected_turn: timedelta) -> None:
        self._apply_expiry(now)
        if self.status is TableStatus.OCCUPIED:
            raise TableNotAvailable(f"La mesa {self.label} ya esta ocupada")
        self.status = TableStatus.OCCUPIED
        self.occupied_since = now
        self.held_at = None
        # Toda retencion caduca. Si el anfitrion no toca 'mesa libre' -y un
        # viernes con 40 personas en la puerta no lo va a hacer siempre- el
        # sistema se recupera solo en vez de quedarse sin mesas a las 9.
        self.auto_release_at = now + expected_turn

    def release(self, now: datetime) -> None:
        """Idempotente a proposito: liberar una mesa ya libre no es un error,
        es un anfitrion tocando dos veces en una tablet con mal wifi."""
        self.status = TableStatus.AVAILABLE
        self.held_by_entry_id = None
        self.held_at = None
        self.occupied_since = None
        self.auto_release_at = None

    def _apply_expiry(self, now: datetime) -> None:
        if self.effective_status(now) is TableStatus.AVAILABLE:
            self.release(now)
