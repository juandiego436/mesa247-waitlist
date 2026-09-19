from __future__ import annotations

import re
from dataclasses import dataclass

from waitlist.domain.errors import InvalidValue


@dataclass(frozen=True, slots=True)
class _CountryRule:
    calling_code: str
    national_length: int
    mobile_prefix: str


# Solo los cuatro paises donde opera Mesa247. Anadir uno es una linea; no hace
# falta arrastrar una libreria de numeracion mundial para cuatro reglas.
_RULES: dict[str, _CountryRule] = {
    "PE": _CountryRule("51", 9, "9"),
    "CL": _CountryRule("56", 9, "9"),
    "EC": _CountryRule("593", 9, "9"),
    "CO": _CountryRule("57", 10, "3"),
}

# Los codigos mas largos primero: '57' es prefijo de nada, pero '593' empieza
# por '59' y hay que probar el largo antes que el corto.
_BY_LENGTH = sorted(_RULES.items(), key=lambda kv: -len(kv[1].calling_code))

_NON_DIGITS = re.compile(r"[^\d]")


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """Un movil en formato E.164, normalizado al construirse.

    Se valida que sea MOVIL, no solo que sea un numero valido: el unico motivo
    por el que pedimos el telefono es avisar por WhatsApp o SMS. Un fijo en la
    cola es un comensal que nunca se entera de que su mesa esta lista, y eso no
    se descubre hasta el viernes por la noche.
    """

    e164: str

    @classmethod
    def parse(cls, raw: str, default_country: str) -> "PhoneNumber":
        if default_country not in _RULES:
            raise InvalidValue(f"Pais no soportado: {default_country!r}")
        if raw is None or not str(raw).strip():
            raise InvalidValue("El telefono es obligatorio")

        text = str(raw).strip()
        international = text.startswith("+") or text.startswith("00")
        digits = _NON_DIGITS.sub("", text)
        if text.startswith("00"):
            digits = digits[2:]

        if not digits:
            raise InvalidValue(f"Telefono sin digitos: {raw!r}")

        if international:
            country, national = cls._split_international(digits, raw)
        else:
            country = default_country
            national = digits.lstrip("0")

        rule = _RULES[country]
        if len(national) != rule.national_length:
            raise InvalidValue(
                f"Un movil de {country} tiene {rule.national_length} digitos, "
                f"recibimos {len(national)}: {raw!r}"
            )
        if not national.startswith(rule.mobile_prefix):
            raise InvalidValue(
                f"No parece un movil de {country} (deberia empezar por "
                f"{rule.mobile_prefix}): {raw!r}"
            )
        return cls(f"+{rule.calling_code}{national}")

    @staticmethod
    def _split_international(digits: str, raw: str) -> tuple[str, str]:
        for country, rule in _BY_LENGTH:
            if not digits.startswith(rule.calling_code):
                continue
            national = digits[len(rule.calling_code):].lstrip("0")
            if len(national) == rule.national_length:
                return country, national
        raise InvalidValue(
            f"Prefijo internacional no soportado (solo PE, CL, EC, CO): {raw!r}"
        )

    @property
    def country(self) -> str:
        for country, rule in _BY_LENGTH:
            if self.e164.startswith(f"+{rule.calling_code}"):
                return country
        return "??"

    @property
    def country_code(self) -> str:
        return _RULES[self.country].calling_code if self.country in _RULES else ""

    def masked(self) -> str:
        """Lo unico que puede salir por la API. Deja ver los ultimos 3 digitos
        para que el anfitrion reconozca a quien tiene delante, sin exponer una
        lista de 142 moviles a quien escanee el QR."""
        return f"+{self.country_code} ****** {self.e164[-3:]}"

    def __str__(self) -> str:
        return self.e164
