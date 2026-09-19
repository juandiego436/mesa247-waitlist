"""La posicion es una proyeccion, no un campo. Estos tests existen para que
nadie la 'optimice' guardandola en una columna."""
from __future__ import annotations

from conftest import make_entry, make_table, minutes
from waitlist.domain.services.queue_view import (
    build_queue_view,
    estimate_wait_for_newcomer,
    ordered_queue,
)
from waitlist.domain.services.seating_service import SeatingService

SEATING = SeatingService()


def test_la_cola_es_orden_de_llegada(now):
    tarde = make_entry(name="Andres V.", at=now + minutes(10))
    pronto = make_entry(name="Carla M.", at=now)
    assert [e.guest_name.short() for e in ordered_queue([tarde, pronto])] == [
        "Carla M.",
        "Andres V.",
    ]


def test_sentar_a_uno_sube_a_todos_los_de_atras_sin_escribir_nada(now):
    """El motivo real de no guardar la posicion: si fuera una columna, esto
    serian 40 UPDATE con dos anfitriones tocando la tablet a la vez."""
    cola = [make_entry(at=now + minutes(i)) for i in range(5)]
    primero, table = cola[0], make_table()
    SEATING.call_for_table(primero, table, now)
    SEATING.seat(primero, table, now)

    posiciones = {v.entry.id: v.position for v in build_queue_view(cola, now)}
    assert primero.id not in posiciones          # ya no esta en la cola
    assert posiciones[cola[1].id] == 1           # subio solo


def test_a_quien_ya_llamaron_no_le_queda_espera(now):
    cola = [make_entry(at=now + minutes(i)) for i in range(3)]
    table = make_table()
    SEATING.call_for_table(cola[0], table, now)

    vista = {v.entry.id: v.estimated_wait_minutes for v in build_queue_view(cola, now)}
    assert vista[cola[0].id] == 0
    assert vista[cola[1].id] == 0     # es el primero que de verdad espera
    assert vista[cola[2].id] == 8


def test_lo_que_se_le_promete_al_que_llega(now):
    cola = [make_entry(at=now + minutes(i)) for i in range(3)]
    assert estimate_wait_for_newcomer(cola) == 24  # 3 grupos x 8 min
