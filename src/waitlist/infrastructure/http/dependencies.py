"""El unico sitio donde se decide que adaptador entra en cada puerto.

Todo el cableado vive aqui. Cambiar SQLite por MySQL, o el notificador de log
por WhatsApp, es cambiar una linea de este archivo y una variable de entorno:
ni el dominio ni los casos de uso se enteran. Eso es lo que compra la
arquitectura hexagonal, y si no se nota aqui es que no se compro nada.
"""
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status

from waitlist.application.use_cases import guest as guest_uc
from waitlist.application.use_cases import host as host_uc
from waitlist.domain.services.seating_service import SeatingService
from waitlist.infrastructure.clock.system_clock import SystemClock
from waitlist.infrastructure.config.settings import Settings, get_settings
from waitlist.infrastructure.notifications.log_notifier import LogNotifier
from waitlist.infrastructure.persistence.engine import get_engine
from waitlist.infrastructure.persistence.unit_of_work import unit_of_work_factory


@lru_cache(maxsize=1)
def _wiring():
    settings = get_settings()
    engine = get_engine()
    uow_factory = unit_of_work_factory(engine, settings.is_sqlite)
    clock = SystemClock()
    seating = SeatingService(
        hold_window=timedelta(minutes=settings.hold_window_minutes),
        expected_turn=timedelta(minutes=settings.expected_turn_minutes),
    )
    notifier = LogNotifier()
    mpp = settings.minutes_per_party
    return {
        "settings": settings,
        "join": guest_uc.JoinQueue(uow_factory, clock, mpp),
        "my_place": guest_uc.ViewMyPlace(uow_factory, clock, mpp),
        "on_the_way": guest_uc.ConfirmOnTheWay(uow_factory, clock),
        "cancel": guest_uc.CancelMyPlace(uow_factory, clock, seating),
        "board": host_uc.ViewBoard(uow_factory, clock, mpp),
        "call": host_uc.CallForTable(uow_factory, clock, seating, notifier),
        "seat": host_uc.SeatParty(uow_factory, clock, seating),
        "no_show": host_uc.MarkNoShow(uow_factory, clock, seating),
        "remove": host_uc.RemoveFromQueue(uow_factory, clock, seating),
        "release_table": host_uc.ReleaseTable(uow_factory, clock),
        "report": host_uc.BuildDailyReport(uow_factory, clock),
        "uow_factory": uow_factory,
        "clock": clock,
    }


def _get(name: str):
    def dependency():
        return _wiring()[name]

    return dependency


def settings_dep() -> Settings:
    return get_settings()


def require_host(
    x_host_token: str | None = Header(default=None),
    settings: Settings = Depends(settings_dep),
) -> str:
    """Token estatico por local para la tablet de la entrada.

    Para el piloto basta: la tablet es compartida, esta fisicamente en el
    restaurante y no hay nada que auditar por persona. Cuando haya que saber
    QUE anfitrion llamo a quien, esto se cambia por la sesion de El Libro.

    Es una decision reversible, y esta encerrada en esta funcion a proposito:
    cambiarla no toca ni un caso de uso.
    """
    if not x_host_token or x_host_token != settings.host_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tablet no autorizada",
        )
    return x_host_token


join_uc = _get("join")
my_place_uc = _get("my_place")
on_the_way_uc = _get("on_the_way")
cancel_uc = _get("cancel")
board_uc = _get("board")
call_uc = _get("call")
seat_uc = _get("seat")
no_show_uc = _get("no_show")
remove_uc = _get("remove")
release_table_uc = _get("release_table")
report_uc = _get("report")
uow_factory_dep = _get("uow_factory")
clock_dep = _get("clock")
