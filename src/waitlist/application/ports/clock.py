from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """El tiempo es una dependencia, no un detalle.

    El dominio nunca llama a datetime.now(): recibe el instante. Por eso los 50
    tests del dominio pueden mover el reloj 76 minutos sin esperar 76 minutos.
    """

    def now(self) -> datetime:
        """Siempre en UTC y consciente de zona horaria."""
        ...
