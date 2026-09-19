"""La tablet de la entrada. Todo detras del token del local."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from waitlist.application.errors import EntryNotFound, TableNotFound, VenueNotFound
from waitlist.infrastructure.http import dependencies as deps
from waitlist.infrastructure.http.schemas import (
    BoardResponse,
    CallRequest,
    QueueItemResponse,
    ReportResponse,
    TableResponse,
)

router = APIRouter(
    prefix="/api/host",
    tags=["anfitrion"],
    dependencies=[Depends(deps.require_host)],
)


@router.get("/venues/{venue_id}/board", response_model=BoardResponse)
def board(venue_id: str, view=Depends(deps.board_uc), clock=Depends(deps.clock_dep)):
    try:
        data = view(venue_id)
    except VenueNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    now = clock.now()
    etiquetas = {t.id: t.label for t in data.tables}
    return BoardResponse(
        venue_name=data.venue_name,
        service_date=str(data.service_date),
        in_queue=len(data.queue),
        average_wait_minutes=data.average_wait_minutes,
        queue=[
            QueueItemResponse.build(
                item, now, etiquetas.get(item.entry.assigned_table_id)
            )
            for item in data.queue
        ],
        tables=[TableResponse.build(t, now) for t in data.tables],
    )


@router.post("/entries/{entry_id}/call", status_code=status.HTTP_204_NO_CONTENT)
def call(entry_id: str, payload: CallRequest, call_uc=Depends(deps.call_uc)):
    """«Llamar». Retiene la mesa y avisa, en una transaccion.

    `force` existe porque un anfitrion va a sentar a 5 personas en una mesa de 4
    y tiene razon al hacerlo. Si el sistema lo impide, la tablet estorba y vuelve
    el cuaderno.
    """
    try:
        call_uc(entry_id, payload.table_id, payload.force)
    except (EntryNotFound, TableNotFound) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/entries/{entry_id}/seat", status_code=status.HTTP_204_NO_CONTENT)
def seat(entry_id: str, seat_uc=Depends(deps.seat_uc)):
    try:
        seat_uc(entry_id)
    except EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/entries/{entry_id}/no-show", status_code=status.HTTP_204_NO_CONTENT)
def no_show(entry_id: str, no_show_uc=Depends(deps.no_show_uc)):
    try:
        no_show_uc(entry_id)
    except EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/entries/{entry_id}/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove(entry_id: str, remove_uc=Depends(deps.remove_uc)):
    try:
        remove_uc(entry_id)
    except EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/tables/{table_id}/release", status_code=status.HTTP_204_NO_CONTENT)
def release_table(table_id: str, release=Depends(deps.release_table_uc)):
    """«Mesa libre». La pantalla que le falta al prototipo y sin la cual el
    sistema se queda sin mesas que asignar a media noche."""
    try:
        release(table_id)
    except TableNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/venues/{venue_id}/report", response_model=ReportResponse)
def report(
    venue_id: str, service_date: str | None = None, build=Depends(deps.report_uc)
):
    """El cierre del dia. En el piloto se abre; el envio por correo es un
    adaptador de la semana 2, y necesita saber a que hora cierra cada local en
    dos husos horarios distintos."""
    try:
        return ReportResponse.build(build(venue_id, service_date))
    except VenueNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
