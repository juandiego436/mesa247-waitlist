from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from waitlist.domain.entities.table import Table, TableStatus
from waitlist.domain.entities.waitlist_entry import (
    CancelledBy,
    WaitlistEntry,
    WaitlistStatus,
)
from waitlist.domain.value_objects.guest_name import GuestName
from waitlist.domain.value_objects.ids import EntryId, TableId, VenueId
from waitlist.domain.value_objects.party_size import PartySize
from waitlist.domain.value_objects.phone_number import PhoneNumber
from waitlist.domain.value_objects.public_token import PublicToken
from waitlist.domain.value_objects.service_date import ServiceDate


def to_db_time(value: datetime | None) -> datetime | None:
    """MySQL DATETIME no guarda zona horaria.

    Guardamos siempre UTC sin tzinfo y la volvemos a poner al leer. Si esta
    conversion se hace solo a medias, las esperas salen desplazadas cinco horas
    y nadie entiende por que.
    """
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def from_db_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=timezone.utc)


# --- WaitlistEntry ------------------------------------------------------


def entry_to_row(entry: WaitlistEntry) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "venue_id": str(entry.venue_id),
        "service_date": entry.service_date.value,
        "public_token": entry.public_token.value,
        "guest_name": entry.guest_name.value,
        "phone_e164": entry.phone.e164,
        "party_size": entry.party_size.value,
        "status": entry.status.value,
        "joined_at": to_db_time(entry.joined_at),
        "called_at": to_db_time(entry.called_at),
        "on_the_way_at": to_db_time(entry.on_the_way_at),
        "hold_expires_at": to_db_time(entry.hold_expires_at),
        "call_count": entry.call_count,
        "closed_at": to_db_time(entry.closed_at),
        "cancelled_by": entry.cancelled_by.value if entry.cancelled_by else None,
        "assigned_table_id": (
            str(entry.assigned_table_id) if entry.assigned_table_id else None
        ),
        "table_assigned_at": to_db_time(entry.table_assigned_at),
        "seated_over_capacity": entry.seated_over_capacity,
        "quoted_wait_minutes": entry.quoted_wait_minutes,
        "version": entry.version,
    }


def row_to_entry(row: Mapping[str, Any]) -> WaitlistEntry:
    return WaitlistEntry(
        id=EntryId.parse(row["id"]),
        venue_id=VenueId.parse(row["venue_id"]),
        service_date=ServiceDate.parse(row["service_date"]),
        guest_name=GuestName.parse(row["guest_name"]),
        # Ya viene normalizado: se guardo en E.164 al entrar en la cola.
        phone=PhoneNumber(row["phone_e164"]),
        party_size=PartySize(row["party_size"]),
        public_token=PublicToken(row["public_token"]),
        joined_at=from_db_time(row["joined_at"]),
        status=WaitlistStatus(row["status"]),
        called_at=from_db_time(row["called_at"]),
        on_the_way_at=from_db_time(row["on_the_way_at"]),
        hold_expires_at=from_db_time(row["hold_expires_at"]),
        call_count=row["call_count"],
        closed_at=from_db_time(row["closed_at"]),
        cancelled_by=CancelledBy(row["cancelled_by"]) if row["cancelled_by"] else None,
        assigned_table_id=(
            TableId.parse(row["assigned_table_id"])
            if row["assigned_table_id"]
            else None
        ),
        table_assigned_at=from_db_time(row["table_assigned_at"]),
        seated_over_capacity=bool(row["seated_over_capacity"]),
        quoted_wait_minutes=row["quoted_wait_minutes"],
        version=row["version"],
    )


# --- Table --------------------------------------------------------------


def table_to_row(table: Table) -> dict[str, Any]:
    return {
        "id": str(table.id),
        "venue_id": str(table.venue_id),
        "external_ref": table.external_ref,
        "label": table.label,
        "seats": table.seats,
        "status": table.status.value,
        "held_by_entry_id": (
            str(table.held_by_entry_id) if table.held_by_entry_id else None
        ),
        "held_at": to_db_time(table.held_at),
        "occupied_since": to_db_time(table.occupied_since),
        "auto_release_at": to_db_time(table.auto_release_at),
        "version": table.version,
    }


def row_to_table(row: Mapping[str, Any]) -> Table:
    return Table(
        id=TableId.parse(row["id"]),
        venue_id=VenueId.parse(row["venue_id"]),
        label=row["label"],
        seats=row["seats"],
        status=TableStatus(row["status"]),
        held_by_entry_id=(
            EntryId.parse(row["held_by_entry_id"]) if row["held_by_entry_id"] else None
        ),
        held_at=from_db_time(row["held_at"]),
        occupied_since=from_db_time(row["occupied_since"]),
        auto_release_at=from_db_time(row["auto_release_at"]),
        external_ref=row["external_ref"],
        version=row["version"],
    )
