from __future__ import annotations

import secrets
from dataclasses import dataclass

from waitlist.domain.errors import InvalidValue

_BYTES = 32


@dataclass(frozen=True, slots=True)
class PublicToken:
    """La llave del comensal para ver su propia posicion.

    El comensal no tiene cuenta: escanea un QR y ya. Si la URL de 'mi posicion'
    llevara el id de la entrada, cualquiera iterando ids se lleva los nombres y
    telefonos de los 142 comensales del viernes. Este token opaco es lo unico
    que separa al publico de esa lista.
    """

    value: str

    @classmethod
    def new(cls) -> "PublicToken":
        return cls(secrets.token_urlsafe(_BYTES))

    @classmethod
    def parse(cls, raw: str) -> "PublicToken":
        text = str(raw or "").strip()
        if len(text) < 20:
            raise InvalidValue("Token invalido")
        return cls(text)

    def matches(self, candidate: str) -> bool:
        """Comparacion en tiempo constante: comparar con == filtra el token
        caracter a caracter por el tiempo de respuesta."""
        return secrets.compare_digest(self.value, str(candidate or ""))

    def __str__(self) -> str:
        return self.value
