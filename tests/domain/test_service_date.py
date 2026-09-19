"""La jornada de servicio. Es la decision que no se puede deshacer: si se
guarda mal, el reporte de un local esta mal para siempre."""
from __future__ import annotations

from datetime import datetime, timezone

from waitlist.domain.value_objects.service_date import ServiceDate

LIMA, SANTIAGO = "America/Lima", "America/Santiago"


def test_el_mismo_instante_cae_en_dias_distintos_segun_el_local():
    """Lima y Santiago tienen dos horas de diferencia. A las 03:30 UTC son las
    22:30 del 11 en Lima y las 00:30 del 12 en Santiago."""
    instante = datetime(2025, 9, 12, 3, 30, tzinfo=timezone.utc)

    assert str(ServiceDate.for_venue(instante, LIMA)) == "2025-09-11"
    assert str(ServiceDate.for_venue(instante, SANTIAGO)) == "2025-09-11"


def test_la_madrugada_pertenece_a_la_noche_anterior():
    """La una y media de la madrugada del sabado sigue siendo el viernes. Si la
    jornada cortara a medianoche, el reporte perderia la hora mas cargada."""
    madrugada = datetime(2025, 9, 13, 6, 30, tzinfo=timezone.utc)  # 01:30 en Lima
    assert str(ServiceDate.for_venue(madrugada, LIMA)) == "2025-09-12"


def test_despues_de_las_cinco_ya_es_la_jornada_nueva():
    manana = datetime(2025, 9, 13, 12, 0, tzinfo=timezone.utc)  # 07:00 en Lima
    assert str(ServiceDate.for_venue(manana, LIMA)) == "2025-09-13"
