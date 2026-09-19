from __future__ import annotations

import re
from dataclasses import dataclass

from waitlist.domain.errors import InvalidValue

_MAX_LENGTH = 80
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class GuestName:
    """El nombre tal como lo escribio el comensal, limpio.

    Acepta 'Familia Rojas' y 'Lucia y Ana' como aparecen en el prototipo: no es
    un campo de identidad, es como el anfitrion va a llamarlos en voz alta.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> "GuestName":
        if raw is None:
            raise InvalidValue("El nombre es obligatorio")
        cleaned = _WHITESPACE.sub(" ", str(raw)).strip()
        if not cleaned:
            raise InvalidValue("El nombre es obligatorio")
        if len(cleaned) > _MAX_LENGTH:
            raise InvalidValue(f"El nombre supera {_MAX_LENGTH} caracteres")
        return cls(cleaned)

    def short(self) -> str:
        """'Carla Mendoza' -> 'Carla M.', como la pantalla del anfitrion."""
        parts = self.value.split(" ")
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} {parts[1][0].upper()}."

    def __str__(self) -> str:
        return self.value
