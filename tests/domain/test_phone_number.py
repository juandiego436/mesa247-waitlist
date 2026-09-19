"""Telefonos. El unico motivo por el que los pedimos es avisar; un fijo en la
cola es alguien que nunca se entera de que su mesa esta lista."""
from __future__ import annotations

import pytest

from waitlist.domain.errors import InvalidValue
from waitlist.domain.value_objects.phone_number import PhoneNumber


@pytest.mark.parametrize(
    "escrito, pais, esperado",
    [
        ("+51 987 654 321", "PE", "+51987654321"),
        ("987654321", "PE", "+51987654321"),
        ("0051 987654321", "PE", "+51987654321"),
        ("(987) 654-321", "PE", "+51987654321"),
        ("+56 9 8765 4321", "CL", "+56987654321"),
        ("0912345678", "EC", "+593912345678"),     # troncal nacional
        ("+593 91234 5678", "EC", "+593912345678"),
        ("300 123 4567", "CO", "+573001234567"),
    ],
)
def test_normaliza_a_e164_en_los_cuatro_paises(escrito, pais, esperado):
    assert PhoneNumber.parse(escrito, pais).e164 == esperado


def test_el_comensal_de_santiago_escribe_como_quiere(now=None):
    """El QR de Casa Mediterranea no sabe que el comensal viene de Lima."""
    assert PhoneNumber.parse("+51987654321", "CL").country == "PE"


@pytest.mark.parametrize(
    "malo, pais",
    [
        ("12345", "PE"),            # corto
        ("012345678", "PE"),        # no es movil
        ("+34 600 123 456", "PE"),  # pais fuera del piloto
        ("", "PE"),
        ("no soy un numero", "PE"),
    ],
)
def test_rechaza_lo_que_no_sirve_para_avisar(malo, pais):
    with pytest.raises(InvalidValue):
        PhoneNumber.parse(malo, pais)


def test_nunca_se_expone_el_numero_completo():
    """142 moviles detras de un QR publico."""
    enmascarado = PhoneNumber.parse("+51987654321", "PE").masked()
    assert "987654" not in enmascarado
    assert enmascarado.endswith("321")
