from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from waitlist.domain.entities.waitlist_entry import WaitlistEntry


@dataclass(frozen=True, slots=True)
class Notification:
    to: str
    body: str
    template: str


class Notifier(Protocol):
    """Como se entera el comensal.

    En el piloto el adaptador solo registra: la plantilla de WhatsApp necesita
    aprobacion de Meta, que tarda dias y a veces la rechazan. El canal real
    durante el piloto es la pantalla del propio comensal. Cuando la plantilla
    este aprobada, se cambia el adaptador y nada mas.
    """

    def table_is_ready(self, entry: WaitlistEntry, venue_name: str) -> None: ...
