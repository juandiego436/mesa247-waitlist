"""Pydantic vive SOLO aqui. El dominio no sabe que existe."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from waitlist.application.use_cases.guest import GuestView
from waitlist.domain.entities.table import Table
from waitlist.domain.reports.daily_report import DailyReport
from waitlist.domain.services.queue_view import QueuePosition


class JoinRequest(BaseModel):
    venue_id: str
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=6, max_length=25)
    party_size: int = Field(ge=1, le=20)


class GuestPlaceResponse(BaseModel):
    """Lo que ve el comensal en su movil.

    Contiene SOLO su propia entrada. Este endpoint es completamente publico -lo
    abre cualquiera que escanee el QR- y detras hay 142 nombres y telefonos.
    """

    token: str
    venue_name: str
    guest_name: str
    party_size: int
    status: str
    position: int | None
    estimated_wait_minutes: int | None
    ahead: int
    joined_at: datetime
    table_label: str | None = None
    hold_expires_at: datetime | None = None
    on_the_way: bool = False

    @classmethod
    def build(cls, view: GuestView, table_label: str | None = None) -> "GuestPlaceResponse":
        e = view.entry
        return cls(
            token=e.public_token.value,
            venue_name=view.venue_name,
            guest_name=e.guest_name.value,
            party_size=e.party_size.value,
            status=e.status.value,
            position=view.position,
            estimated_wait_minutes=view.estimated_wait_minutes,
            ahead=view.ahead,
            joined_at=e.joined_at,
            table_label=table_label,
            hold_expires_at=e.hold_expires_at,
            on_the_way=e.on_the_way_at is not None,
        )


class QueueItemResponse(BaseModel):
    """La fila de la tablet del anfitrion.

    El telefono va enmascarado: el anfitrion necesita reconocer a quien tiene
    delante, no una lista exportable de moviles.
    """

    entry_id: str
    position: int
    name: str
    party_size: int
    waited_minutes: int
    estimated_wait_minutes: int
    status: str
    phone_masked: str
    table_label: str | None
    called_at: datetime | None
    hold_expired: bool
    on_the_way: bool

    @classmethod
    def build(
        cls, item: QueuePosition, now: datetime, table_label: str | None
    ) -> "QueueItemResponse":
        e = item.entry
        return cls(
            entry_id=str(e.id),
            position=item.position,
            name=e.guest_name.short(),
            party_size=e.party_size.value,
            waited_minutes=e.waited_minutes(now),
            estimated_wait_minutes=item.estimated_wait_minutes,
            status=e.status.value,
            phone_masked=e.phone.masked(),
            table_label=table_label,
            called_at=e.called_at,
            hold_expired=e.hold_has_expired(now),
            on_the_way=e.on_the_way_at is not None,
        )


class TableResponse(BaseModel):
    table_id: str
    label: str
    seats: int
    status: str
    held_by_entry_id: str | None
    free_at: datetime | None

    @classmethod
    def build(cls, table: Table, now: datetime) -> "TableResponse":
        return cls(
            table_id=str(table.id),
            label=table.label,
            seats=table.seats,
            # El estado EFECTIVO, con la caducidad ya aplicada. Es la diferencia
            # entre una tablet usable a las nueve y un ladrillo.
            status=table.effective_status(now).value,
            held_by_entry_id=str(table.held_by_entry_id)
            if table.held_by_entry_id
            else None,
            free_at=table.auto_release_at,
        )


class BoardResponse(BaseModel):
    venue_name: str
    service_date: str
    in_queue: int
    average_wait_minutes: int | None
    queue: list[QueueItemResponse]
    tables: list[TableResponse]


class CallRequest(BaseModel):
    table_id: str
    force: bool = False


class ReportResponse(BaseModel):
    service_date: str
    joined: int
    seated: int
    left_without_seating: int
    no_show: int
    still_waiting: int
    average_wait_minutes: int | None
    median_wait_minutes: int | None
    quoted_vs_real_delta: int | None
    adds_up: bool

    @classmethod
    def build(cls, report: DailyReport) -> "ReportResponse":
        return cls(
            service_date=str(report.service_date),
            joined=report.joined,
            seated=report.seated,
            left_without_seating=report.left_without_seating,
            no_show=report.no_show,
            still_waiting=report.still_waiting,
            average_wait_minutes=report.average_wait_minutes,
            median_wait_minutes=report.median_wait_minutes,
            quoted_vs_real_delta=report.quoted_vs_real_delta,
            adds_up=report.adds_up(),
        )


class VenueResponse(BaseModel):
    venue_id: str
    name: str
    timezone: str
    country: str
