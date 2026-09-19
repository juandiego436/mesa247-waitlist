"""El cierre del dia, contra los numeros exactos del prototipo."""
from __future__ import annotations

from conftest import VENUE, make_entry, make_table, minutes
from waitlist.domain.reports.daily_report import DailyReport
from waitlist.domain.services.seating_service import SeatingService

SEATING = SeatingService()


def _jornada(now, sentados=97, se_fueron=31, no_vinieron=14, aun_en_cola=0):
    entries = []
    for _ in range(sentados):
        e, t = make_entry(at=now, quoted=25), make_table()
        SEATING.call_for_table(e, t, now)
        SEATING.seat(e, t, now + minutes(34))
        entries.append(e)
    for _ in range(se_fueron):
        e = make_entry(at=now)
        e.cancel_by_guest(now + minutes(20))
        entries.append(e)
    for _ in range(no_vinieron):
        e, t = make_entry(at=now), make_table()
        SEATING.call_for_table(e, t, now)
        SEATING.mark_no_show(e, t, now + minutes(11))
        entries.append(e)
    entries.extend(make_entry(at=now) for _ in range(aun_en_cola))
    return entries


def test_reproduce_la_pantalla_cinco_del_prototipo(now):
    entries = _jornada(now)
    report = DailyReport.from_entries(
        VENUE, entries[0].service_date, entries, now + minutes(300)
    )

    assert report.joined == 142
    assert report.seated == 97
    assert report.left_without_seating == 31
    assert report.no_show == 14
    assert report.average_wait_minutes == 34
    assert report.adds_up()


def test_los_que_siguen_en_cola_al_cierre_no_desaparecen(now):
    """Los numeros del prototipo suman exacto (97+31+14=142), o sea que asumen
    que al cierre no queda nadie. En la vida real quedan, y una entrada activa
    con la fecha de ayer es un fantasma en la cola de manana."""
    entries = _jornada(now, aun_en_cola=6)
    report = DailyReport.from_entries(
        VENUE, entries[0].service_date, entries, now + minutes(300)
    )

    assert report.joined == 148
    assert report.still_waiting == 6
    assert report.adds_up()


def test_la_media_se_la_lleva_un_caso_raro_y_la_mediana_no(now):
    """Por esto calculamos las dos. El gerente va a mirar este numero."""
    entries = []
    for _ in range(9):
        e = make_entry(at=now)
        e.seat(now + minutes(20))
        entries.append(e)
    tardon = make_entry(at=now)
    tardon.seat(now + minutes(200))
    entries.append(tardon)

    report = DailyReport.from_entries(
        VENUE, entries[0].service_date, entries, now + minutes(300)
    )
    assert report.average_wait_minutes == 38   # el tardon la inflo
    assert report.median_wait_minutes == 20    # la mediana aguanta


def test_compara_lo_prometido_con_lo_real(now):
    """Prometimos 25 y esperaron 34: nueve minutos de mas. Ese numero no se
    puede reconstruir despues si no se guarda al unirse."""
    entries = _jornada(now, sentados=10, se_fueron=0, no_vinieron=0)
    report = DailyReport.from_entries(
        VENUE, entries[0].service_date, entries, now + minutes(300)
    )
    assert report.quoted_vs_real_delta == 9


def test_jornada_vacia_no_divide_entre_cero(now):
    report = DailyReport.from_entries(
        VENUE, make_entry(at=now).service_date, [], now
    )
    assert report.joined == 0
    assert report.average_wait_minutes is None
    assert report.adds_up()
