from __future__ import annotations

import re
from dataclasses import dataclass

from waitlist.domain.errors import InvalidValue

_MAX_LENGTH = 80
_WHITESPACE = re.compile(r"\s+")

# Nombres que no son "nombre apellido" y no se deben abreviar.
_COLECTIVO = re.compile(
    r"^(familia|flia\.?|grupo|mesa|sr\.?|sra\.?)\s|\s(y|e|and|&|\+)\s", re.IGNORECASE
)


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
        """Como la pantalla del anfitrion: 'Carla Mendoza' -> 'Carla M.'

        Pero 'Familia Rojas' y 'Lucia y Ana' se quedan enteros, que es como
        aparecen en el prototipo. Abreviar un colectivo da 'Lucia Y.', que no
        es solo feo: es un nombre que el anfitrion no puede gritar en la puerta.
        """
        parts = self.value.split(" ")
        if len(parts) == 1:
            return parts[0]
        # search y no match: la primera rama ya trae su propio ^, pero la del
        # conector tiene que poder disparar en medio del nombre.
        if _COLECTIVO.search(self.value):
            return self.value
        return f"{parts[0]} {parts[1][0].upper()}."

    def __str__(self) -> str:
        return self.value
