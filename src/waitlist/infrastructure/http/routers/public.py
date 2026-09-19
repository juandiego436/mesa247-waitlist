"""Lo que abre cualquiera que escanee el QR de la puerta.

Sin login, sin sesion, sin cookies. Cada endpoint devuelve SOLO la entrada de
quien trae el token, y el token es opaco: si aqui se colara un id secuencial o
una lista, seria una fuga de 142 nombres y telefonos un viernes por la noche.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from waitlist.application.errors import AlreadyInQueue, EntryNotFound, VenueNotFound
from waitlist.infrastructure.http import dependencies as deps
from waitlist.infrastructure.http.schemas import (
    GuestPlaceResponse,
    JoinRequest,
    VenueResponse,
)

router = APIRouter(prefix="/api/public", tags=["comensal"])


@router.get("/venues", response_model=list[VenueResponse])
def list_venues(uow_factory=Depends(deps.uow_factory_dep)):
    """Solo para que el QR de demo sepa a que local apunta. En produccion el QR
    ya lleva el venue_id y esto no hace falta."""
    with uow_factory() as uow:
        return [
            VenueResponse(
                venue_id=str(v.id), name=v.name, timezone=v.timezone, country=v.country
            )
            for v in uow.venues.list_all()
        ]


@router.post(
    "/queue", response_model=GuestPlaceResponse, status_code=status.HTTP_201_CREATED
)
def join_queue(payload: JoinRequest, join=Depends(deps.join_uc)):
    try:
        view = join(payload.venue_id, payload.name, payload.phone, payload.party_size)
    except VenueNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except AlreadyInQueue as exc:
        # 409 con el token de la entrada que ya tenia. Quien toca 'Unirme' cinco
        # veces desde la puerta no quiere un error, quiere ver su puesto.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "token": exc.token},
        ) from exc
    return GuestPlaceResponse.build(view)


@router.get("/queue/{token}", response_model=GuestPlaceResponse)
def my_place(token: str, my_place_uc=Depends(deps.my_place_uc), uow_factory=Depends(deps.uow_factory_dep)):
    """El endpoint mas llamado del sistema: la pantalla del comensal lo consulta
    cada pocos segundos, con datos moviles y wifi malo. Por eso la respuesta es
    pequena y plana."""
    try:
        view = my_place_uc(token)
    except EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    etiqueta = None
    if view.entry.assigned_table_id:
        with uow_factory() as uow:
            mesa = uow.tables.get(view.entry.assigned_table_id)
            etiqueta = mesa.label if mesa else None
    return GuestPlaceResponse.build(view, etiqueta)


@router.post("/queue/{token}/on-the-way", status_code=status.HTTP_204_NO_CONTENT)
def on_the_way(token: str, confirm=Depends(deps.on_the_way_uc)):
    try:
        confirm(token)
    except EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/queue/{token}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel(token: str, cancel_uc=Depends(deps.cancel_uc)):
    """«Ya no voy». Es el boton que resuelve el dolor declarado del encargo: la
    gente que se va sin avisar."""
    try:
        cancel_uc(token)
    except EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
