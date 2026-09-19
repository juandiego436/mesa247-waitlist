from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from waitlist.domain.errors import InvalidValue


@dataclass(frozen=True, slots=True)
class _UuidId:
    """Identidad opaca generada en el dominio, no por la base de datos.

    Que el id nazca aca y no en un AUTO_INCREMENT permite construir una
    entidad completa y valida sin haber tocado MySQL, que es lo que hace que
    los tests del dominio corran en un segundo.
    """

    value: UUID

    @classmethod
    def new(cls) -> "_UuidId":
        return cls(uuid4())

    @classmethod
    def parse(cls, raw: object) -> "_UuidId":
        try:
            return cls(UUID(str(raw)))
        except (ValueError, AttributeError, TypeError) as exc:
            raise InvalidValue(f"{cls.__name__} invalido: {raw!r}") from exc

    def __str__(self) -> str:
        return str(self.value)


# Tipos distintos a proposito: el __eq__ que genera dataclass compara la clase,
# asi que un EntryId nunca sera igual a un TableId aunque lleven el mismo UUID.
class EntryId(_UuidId):
    pass


class TableId(_UuidId):
    pass


class VenueId(_UuidId):
    pass
