from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from waitlist.domain.errors import InvalidValue

# La jornada de servicio no cambia a medianoche. Un local que cierra a las 2 de
# la madrugada sigue trabajando el viernes a la 1:30. Si el corte fuera a las
# 00:00, el reporte del viernes perderia la ultima hora y media, que es
# justamente la mas cargada.
DAY_STARTS_AT_HOUR = 5


@dataclass(frozen=True, slots=True)
class ServiceDate:
    """La jornada a la que pertenece una entrada.

    Se calcula UNA vez, al unirse, con la zona horaria del local, y se guarda.
    Derivarla en cada consulta a partir del instante UTC es la forma de que el
    reporte de La Terraza Azul y el de Casa Mediterranea no cuadren nunca: el
    mismo instante es el 11 en Lima y el 12 en Santiago.
    """

    value: date

    @classmethod
    def for_venue(cls, moment: datetime, timezone_name: str) -> "ServiceDate":
        if moment.tzinfo is None:
            raise InvalidValue("El instante debe ser consciente de zona horaria")
        try:
            local = moment.astimezone(ZoneInfo(timezone_name))
        except Exception as exc:
            raise InvalidValue(f"Zona horaria invalida: {timezone_name!r}") from exc
        if local.hour < DAY_STARTS_AT_HOUR:
            local -= timedelta(days=1)
        return cls(local.date())

    @classmethod
    def parse(cls, raw: object) -> "ServiceDate":
        if isinstance(raw, ServiceDate):
            return raw
        if isinstance(raw, datetime):
            return cls(raw.date())
        if isinstance(raw, date):
            return cls(raw)
        try:
            return cls(date.fromisoformat(str(raw)))
        except ValueError as exc:
            raise InvalidValue(f"Fecha de jornada invalida: {raw!r}") from exc

    def __str__(self) -> str:
        return self.value.isoformat()
