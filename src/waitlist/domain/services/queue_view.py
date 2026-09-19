from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from waitlist.domain.entities.waitlist_entry import WaitlistEntry, WaitlistStatus

# Cuanto tarda de media en liberarse una mesa por grupo que hay delante.
# Es un numero grueso a proposito: con tres locales no tenemos historico para
# afinarlo, y prometer 25 minutos con dos decimales es prometer precision que
# no tenemos. Cuando haya datos del piloto, este es el primer numero a revisar.
DEFAULT_MINUTES_PER_PARTY = 8


@dataclass(frozen=True, slots=True)
class QueuePosition:
    entry: WaitlistEntry
    position: int
    estimated_wait_minutes: int


def ordered_queue(entries: list[WaitlistEntry]) -> list[WaitlistEntry]:
    """La cola son los activos por orden de llegada.

    Ordenar por joined_at y no por una columna 'position' es deliberado: la
    posicion es una proyeccion de la cola entera, no un atributo de la entrada.
    Guardarla obligaria a reescribir 40 filas cada vez que alguien se sienta.
    """
    active = [e for e in entries if e.is_active()]
    return sorted(active, key=lambda e: (e.joined_at, str(e.id)))


def build_queue_view(
    entries: list[WaitlistEntry],
    now: datetime,
    minutes_per_party: int = DEFAULT_MINUTES_PER_PARTY,
) -> list[QueuePosition]:
    view: list[QueuePosition] = []
    waiting_ahead = 0
    for index, entry in enumerate(ordered_queue(entries), start=1):
        # A quien ya fue llamado le queda 0: su mesa esta lista, no espera cola.
        if entry.status is WaitlistStatus.CALLED:
            estimate = 0
        else:
            estimate = waiting_ahead * minutes_per_party
            waiting_ahead += 1
        view.append(QueuePosition(entry, index, estimate))
    return view


def estimate_wait_for_newcomer(
    entries: list[WaitlistEntry],
    minutes_per_party: int = DEFAULT_MINUTES_PER_PARTY,
) -> int:
    """Lo que le prometemos a quien esta a punto de unirse."""
    waiting = [e for e in ordered_queue(entries) if e.status is WaitlistStatus.WAITING]
    return len(waiting) * minutes_per_party
