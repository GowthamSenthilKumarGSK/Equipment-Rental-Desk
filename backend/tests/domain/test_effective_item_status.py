from datetime import UTC, datetime, timedelta

import pytest

from app.domain.enums import ItemStatus
from app.domain.rules import effective_item_status

T0 = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(hours=47, minutes=59), ItemStatus.RESERVED),
        (timedelta(hours=48), ItemStatus.AVAILABLE),  # expired at read time, no job needed
        (timedelta(hours=48, minutes=1), ItemStatus.AVAILABLE),
    ],
)
def test_reserved_item_becomes_available_when_hold_lapses(elapsed, expected):
    status = effective_item_status(ItemStatus.RESERVED, now=T0 + elapsed, reserved_at=T0)

    assert status == expected


@pytest.mark.parametrize(
    ("offset_from_due", "expected"),
    [
        (timedelta(seconds=-1), ItemStatus.CHECKED_OUT),
        (timedelta(0), ItemStatus.CHECKED_OUT),
        (timedelta(seconds=1), ItemStatus.OVERDUE),
        (timedelta(days=20), ItemStatus.OVERDUE),
    ],
)
def test_checked_out_item_becomes_overdue_after_due_date(offset_from_due, expected):
    due_at = T0 + timedelta(days=7)

    status = effective_item_status(
        ItemStatus.CHECKED_OUT, now=due_at + offset_from_due, due_at=due_at
    )

    assert status == expected


@pytest.mark.parametrize("stored", [ItemStatus.AVAILABLE, ItemStatus.UNDER_MAINTENANCE])
def test_other_states_are_never_changed_by_time(stored):
    assert effective_item_status(stored, now=T0 + timedelta(days=365)) == stored
