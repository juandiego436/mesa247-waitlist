"""La mesa como recurso: donde de verdad se puede romper algo caro.

Un doble-booking no es un bug de datos, son dos grupos de pie delante de la
misma mesa un viernes a las nueve.
"""
from __future__ import annotations

import pytest

from conftest import make_entry, make_table, minutes
from waitlist.domain.entities.table import TableStatus
from waitlist.domain.errors import (
    InvalidTransition,
    TableDoesNotFit,
    TableNotAvailable,
)
from waitlist.domain.services.seating_service import SeatingService

SEATING = SeatingService()


def test_llamar_retiene_la_mesa(now):
    entry, table = make_entry(at=now), make_table()
    SEATING.call_for_table(entry, table, now)

    assert table.status is TableStatus.HELD
    assert table.held_by_entry_id == entry.id
    assert not table.is_available_at(now)


def test_una_mesa_retenida_no_se_puede_dar_a_otro(now):
    """El invariante que cruza las dos entidades."""
    table = make_table()
    primero, segundo = make_entry(at=now), make_entry(at=now)
    SEATING.call_for_table(primero, table, now)

    with pytest.raises(TableNotAvailable):
        SEATING.call_for_table(segundo, table, now)

    assert table.held_by_entry_id == primero.id
    assert segundo.assigned_table_id is None  # no quedo a medias


def test_cancelar_libera_la_mesa_sin_que_nadie_se_acuerde(now):
    entry, table = make_entry(at=now), make_table()
    SEATING.call_for_table(entry, table, now)
    SEATING.cancel_by_guest(entry, table, now + minutes(1))

    assert table.is_available_at(now + minutes(1))
    assert entry.assigned_table_id is None


def test_no_show_libera_la_mesa(now):
    entry, table = make_entry(at=now), make_table()
    SEATING.call_for_table(entry, table, now)
    SEATING.mark_no_show(entry, table, now + minutes(11))

    assert table.status is TableStatus.AVAILABLE


def test_sentar_ocupa_la_mesa(now):
    entry, table = make_entry(at=now), make_table()
    SEATING.call_for_table(entry, table, now)
    SEATING.seat(entry, table, now + minutes(3))

    assert table.status is TableStatus.OCCUPIED
    assert table.occupied_since == now + minutes(3)


def test_la_mesa_ocupada_se_libera_sola_al_leer(now):
    """Sin worker ni cron: la caducidad se calcula, no se escribe.

    Sin esto, a las nueve de la noche las veinte mesas estan marcadas como
    ocupadas, no hay ninguna que asignar y la tablet es un ladrillo.
    """
    entry, table = make_entry(at=now), make_table()
    SEATING.call_for_table(entry, table, now)
    SEATING.seat(entry, table, now)

    assert not table.is_available_at(now + minutes(60))
    assert table.is_available_at(now + minutes(76))  # turno por defecto: 75 min


def test_la_retencion_tambien_caduca(now):
    """Si el anfitrion ni sienta ni marca no-show, la mesa no queda muerta."""
    entry, table = make_entry(at=now), make_table()
    SEATING.call_for_table(entry, table, now)

    assert not table.is_available_at(now + minutes(12))
    assert table.is_available_at(now + minutes(16))  # 10 de ventana + 5 de gracia


def test_no_cabe_el_grupo_salvo_que_el_anfitrion_fuerce(now):
    entry = make_entry(size=5, at=now)
    table = make_table(seats=4)

    with pytest.raises(TableDoesNotFit):
        SEATING.call_for_table(entry, table, now)

    SEATING.call_for_table(entry, table, now, force=True)
    assert entry.seated_over_capacity is True
    assert table.status is TableStatus.HELD


def test_rellamar_a_otra_mesa_suelta_la_primera(now):
    entry = make_entry(at=now)
    primera, segunda = make_table(label="7"), make_table(label="9")
    SEATING.call_for_table(entry, primera, now)
    SEATING.call_for_table(entry, segunda, now + minutes(2), previous_table=primera)

    assert primera.is_available_at(now + minutes(2))
    assert segunda.status is TableStatus.HELD
    assert entry.assigned_table_id == segunda.id


def test_no_se_retiene_mesa_para_alguien_ya_sentado(now):
    """Validar la entrada ANTES de tocar la mesa: si no, retendriamos una mesa
    que despues habria que devolver a mano."""
    entry, table = make_entry(at=now), make_table()
    entry.seat(now)

    with pytest.raises(InvalidTransition):
        SEATING.call_for_table(entry, table, now)

    assert table.status is TableStatus.AVAILABLE
