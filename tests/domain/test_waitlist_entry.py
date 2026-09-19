"""La maquina de estados. Es lo que se rompe un viernes: dos anfitriones con
dos tablets y mal wifi tocando el mismo boton dos veces."""
from __future__ import annotations

import pytest

from conftest import make_entry, make_table, minutes
from waitlist.domain.entities.waitlist_entry import CancelledBy, WaitlistStatus
from waitlist.domain.errors import InvalidTransition


def test_join_deja_al_comensal_esperando_sin_mesa(now):
    entry = make_entry(at=now)
    assert entry.status is WaitlistStatus.WAITING
    assert entry.assigned_table_id is None
    assert entry.is_active()
    assert entry.public_token.value  # llave para ver su propia posicion


def test_llamar_retiene_mesa_y_abre_la_ventana_de_diez_minutos(now):
    entry, table = make_entry(at=now), make_table()
    entry.call_for_table(table_id=table.id, now=now, hold_window=minutes(10))

    assert entry.status is WaitlistStatus.CALLED
    assert entry.assigned_table_id == table.id
    assert entry.call_count == 1
    assert not entry.hold_has_expired(now + minutes(9))
    assert entry.hold_has_expired(now + minutes(10))


def test_la_ventana_vencida_no_cambia_el_estado_sola(now):
    """No hay scheduler: que se venza es informacion para el anfitrion, que es
    quien ve si la persona esta en la puerta. El estado lo decide el."""
    entry, table = make_entry(at=now), make_table()
    entry.call_for_table(table_id=table.id, now=now, hold_window=minutes(10))

    assert entry.hold_has_expired(now + minutes(30))
    assert entry.status is WaitlistStatus.CALLED


def test_volver_a_llamar_reinicia_la_ventana_y_cuenta(now):
    entry, table = make_entry(at=now), make_table()
    entry.call_for_table(table_id=table.id, now=now, hold_window=minutes(10))
    entry.call_for_table(table_id=table.id, now=now + minutes(12), hold_window=minutes(10))

    assert entry.call_count == 2
    assert entry.called_at == now          # la primera llamada, para el reporte
    assert not entry.hold_has_expired(now + minutes(15))


def test_voy_en_camino_es_una_marca_no_un_estado(now):
    entry, table = make_entry(at=now), make_table()
    entry.call_for_table(table_id=table.id, now=now, hold_window=minutes(10))
    entry.confirm_on_the_way(now + minutes(2))

    assert entry.status is WaitlistStatus.CALLED
    assert entry.on_the_way_at == now + minutes(2)


def test_no_se_confirma_sin_haber_sido_llamado(now):
    with pytest.raises(InvalidTransition):
        make_entry(at=now).confirm_on_the_way(now)


def test_el_anfitrion_puede_sentar_sin_llamar(now):
    """Pasa todo el rato: el grupo esta delante y el anfitrion los sienta."""
    entry = make_entry(at=now)
    entry.seat(now + minutes(5))
    assert entry.status is WaitlistStatus.SEATED


@pytest.mark.parametrize("cierre", ["seat", "cancel_by_guest", "remove_by_host"])
def test_los_estados_terminales_son_definitivos(now, cierre):
    """El segundo toque en la tablet muere aqui, no en la base de datos."""
    entry, table = make_entry(at=now), make_table()
    getattr(entry, cierre)(now)

    with pytest.raises(InvalidTransition):
        entry.call_for_table(table_id=table.id, now=now, hold_window=minutes(10))
    with pytest.raises(InvalidTransition):
        entry.seat(now)
    with pytest.raises(InvalidTransition):
        entry.cancel_by_guest(now)


def test_no_show_solo_despues_de_llamar(now):
    entry = make_entry(at=now)
    with pytest.raises(InvalidTransition):
        entry.mark_no_show(now)

    table = make_table()
    entry.call_for_table(table_id=table.id, now=now, hold_window=minutes(10))
    entry.mark_no_show(now + minutes(11))
    assert entry.status is WaitlistStatus.NO_SHOW
    assert entry.cancelled_by is None  # no es lo mismo que irse por su cuenta


def test_quien_cancela_queda_registrado(now):
    guest, host = make_entry(at=now), make_entry(at=now)
    guest.cancel_by_guest(now)
    host.remove_by_host(now)

    assert guest.cancelled_by is CancelledBy.GUEST
    assert host.cancelled_by is CancelledBy.HOST


def test_la_espera_se_congela_al_cerrar(now):
    entry = make_entry(at=now)
    entry.seat(now + minutes(34))
    assert entry.waited_minutes(now + minutes(300)) == 34
