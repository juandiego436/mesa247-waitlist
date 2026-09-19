from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from waitlist.domain.value_objects.ids import VenueId


@dataclass(frozen=True, slots=True)
class VenueProfile:
    """Los datos del local que el dominio necesita para decidir.

    No es una entidad de dominio: el local es de El Libro, nosotros solo lo
    leemos. Por eso vive en la capa de aplicacion y no en domain/.
    """

    id: VenueId
    name: str
    timezone: str
    country: str
    expected_turn_minutes: int


class VenueReader(Protocol):
    def get(self, venue_id: VenueId) -> VenueProfile | None: ...
    def list_all(self) -> list[VenueProfile]: ...
