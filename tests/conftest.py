from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from waitlist.domain.entities.table import Table
from waitlist.domain.entities.waitlist_entry import WaitlistEntry
from waitlist.domain.value_objects.guest_name import GuestName
from waitlist.domain.value_objects.ids import TableId, VenueId
from waitlist.domain.value_objects.party_size import PartySize
from waitlist.domain.value_objects.phone_number import PhoneNumber
from waitlist.domain.value_objects.service_date import ServiceDate

VENUE = VenueId.new()
FRIDAY_9PM = datetime(2025, 9, 12, 2, 0, tzinfo=timezone.utc)  # 21:00 en Lima


@pytest.fixture
def now() -> datetime:
    return FRIDAY_9PM


def make_entry(
    *,
    name: str = "Carla Mendoza",
    phone: str = "+51 987 654 321",
    size: int = 4,
    at: datetime = FRIDAY_9PM,
    venue: VenueId = VENUE,
    quoted: int | None = None,
) -> WaitlistEntry:
    return WaitlistEntry.join(
        venue_id=venue,
        service_date=ServiceDate.for_venue(at, "America/Lima"),
        guest_name=GuestName.parse(name),
        phone=PhoneNumber.parse(phone, "PE"),
        party_size=PartySize.parse(size),
        now=at,
        quoted_wait_minutes=quoted,
    )


def make_table(*, label: str = "7", seats: int = 4, venue: VenueId = VENUE) -> Table:
    return Table(id=TableId.new(), venue_id=venue, label=label, seats=seats)


def minutes(n: int) -> timedelta:
    return timedelta(minutes=n)
