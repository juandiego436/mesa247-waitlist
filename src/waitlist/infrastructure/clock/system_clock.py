from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    """El unico sitio de todo el sistema donde se pregunta la hora."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FrozenClock:
    """Reloj de pruebas. Permite mover el tiempo 76 minutos sin esperarlos."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def advance(self, **kwargs) -> None:
        from datetime import timedelta

        self._moment += timedelta(**kwargs)
