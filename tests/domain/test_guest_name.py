"""Como se ve el nombre en la tablet. La pantalla 4 del prototipo muestra
'Familia Rojas' y 'Lucia y Ana' enteros, y solo abrevia 'Carla M.'"""
from __future__ import annotations

import pytest

from waitlist.domain.errors import InvalidValue
from waitlist.domain.value_objects.guest_name import GuestName


@pytest.mark.parametrize(
    "escrito, en_la_tablet",
    [
        ("Carla Mendoza", "Carla M."),
        ("Jorge Perez Rojas", "Jorge P."),
        ("Carla", "Carla"),
        # Colectivos: abreviarlos da nombres que no se pueden gritar en la puerta
        ("Familia Rojas", "Familia Rojas"),
        ("Lucia y Ana", "Lucia y Ana"),
        ("Pedro e Ines", "Pedro e Ines"),
        ("Ana & Luis", "Ana & Luis"),
    ],
)
def test_como_aparece_en_la_tablet(escrito, en_la_tablet):
    assert GuestName.parse(escrito).short() == en_la_tablet


def test_limpia_lo_que_el_comensal_escribe_con_prisa():
    assert GuestName.parse("  Carla   Mendoza  ").value == "Carla Mendoza"


@pytest.mark.parametrize("malo", ["", "   ", None, "x" * 81])
def test_rechaza_lo_que_no_es_un_nombre(malo):
    with pytest.raises(InvalidValue):
        GuestName.parse(malo)
