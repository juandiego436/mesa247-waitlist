from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from waitlist.domain.entities.waitlist_entry import WaitlistEntry, WaitlistStatus
from waitlist.domain.value_objects.ids import VenueId
from waitlist.domain.value_objects.service_date import ServiceDate


@dataclass(frozen=True, slots=True)
class DailyReport:
    """El cierre del dia. No es una entidad: no tiene identidad ni ciclo de
    vida, es un valor calculado.

    Sale casi gratis porque la entidad quedo bien: 'service_date' explicito da
    la jornada correcta en Lima y en Santiago, y 'cancelled_by' distingue al que
    se fue por su cuenta del que no vino cuando lo llamaron. Sin esos dos
    campos, estos numeros no se pueden reconstruir.
    """

    venue_id: VenueId
    service_date: ServiceDate
    joined: int
    seated: int
    left_without_seating: int
    no_show: int
    still_waiting: int
    average_wait_minutes: int | None
    median_wait_minutes: int | None
    quoted_vs_real_delta: int | None

    @classmethod
    def from_entries(
        cls,
        venue_id: VenueId,
        service_date: ServiceDate,
        entries: Iterable[WaitlistEntry],
        now: datetime,
    ) -> "DailyReport":
        entries = list(entries)
        seated = [e for e in entries if e.status is WaitlistStatus.SEATED]
        waits = sorted(e.waited_minutes(now) for e in seated)

        quoted = [
            e.waited_minutes(now) - e.quoted_wait_minutes
            for e in seated
            if e.quoted_wait_minutes is not None
        ]

        return cls(
            venue_id=venue_id,
            service_date=service_date,
            joined=len(entries),
            seated=len(seated),
            left_without_seating=sum(
                1 for e in entries if e.status is WaitlistStatus.CANCELLED
            ),
            no_show=sum(1 for e in entries if e.status is WaitlistStatus.NO_SHOW),
            # El prototipo asume que al cierre no queda nadie: 97+31+14 = 142,
            # cuadra exacto. En la vida real quedan, y si nadie los cierra son
            # fantasmas que manana aparecen en la cola. Este contador los hace
            # visibles en vez de esconderlos.
            still_waiting=sum(1 for e in entries if e.is_active()),
            average_wait_minutes=_mean(waits),
            median_wait_minutes=_median(waits),
            quoted_vs_real_delta=_mean(quoted),
        )

    def adds_up(self) -> bool:
        """Invariante del reporte: toda entrada esta en exactamente un cubo."""
        return self.joined == (
            self.seated + self.left_without_seating + self.no_show + self.still_waiting
        )


def _mean(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def _median(values: list[int]) -> int | None:
    """El prototipo pide 'espera media' y eso es la media, pero un grupo que
    espero dos horas te mueve ese numero y el gerente va a decidir cosas
    mirandolo. Calculamos las dos y que el producto elija; cuesta una linea."""
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return round((values[mid - 1] + values[mid]) / 2)
