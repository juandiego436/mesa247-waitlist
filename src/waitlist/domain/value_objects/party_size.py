from __future__ import annotations

from dataclasses import dataclass

from waitlist.domain.errors import InvalidValue

MIN_PARTY_SIZE = 1
# Por encima de esto ya no es un walk-in, es un evento, y se reserva por
# telefono. Tope duro para que el '+' de la pantalla no genere basura.
MAX_PARTY_SIZE = 20


@dataclass(frozen=True, slots=True)
class PartySize:
    """Cuantas personas vienen. No es una mesa asignada."""

    value: int

    @classmethod
    def parse(cls, raw: object) -> "PartySize":
        try:
            size = int(raw)
        except (TypeError, ValueError) as exc:
            raise InvalidValue(f"Tamano de grupo invalido: {raw!r}") from exc
        if isinstance(raw, float) and raw != size:
            raise InvalidValue(f"Tamano de grupo invalido: {raw!r}")
        if not MIN_PARTY_SIZE <= size <= MAX_PARTY_SIZE:
            raise InvalidValue(
                f"El grupo debe ser de {MIN_PARTY_SIZE} a {MAX_PARTY_SIZE} "
                f"personas, recibimos {size}"
            )
        return cls(size)

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)
