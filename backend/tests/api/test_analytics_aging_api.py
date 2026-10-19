"""GET /analytics/overdue-aging: bands, fees, blocking, top members and late returns."""

from datetime import timedelta

import pytest

from app.domain.analytics import AGING_BANDS
from tests.api.analytics_helpers import (
    checked_out_loan,
    fetch,
    new_item,
    new_member,
    returned_loan,
)
from tests.builders import NOW

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
SECOND = timedelta(seconds=1)
MICRO = timedelta(microseconds=1)
# 12 Oct 2026 15:30 IST. A 7-day report is 6 Oct 00:00 IST up to 13 Oct 00:00 IST, the week before
# that is 29 Sep 00:00 IST up to 6 Oct 00:00 IST.
CURRENT_START = NOW.replace(hour=0, minute=0) - timedelta(days=6) - timedelta(hours=5, minutes=30)
PREVIOUS_START = CURRENT_START - timedelta(days=7)


def band_of(days_overdue: int) -> int:
    """An independent restatement of the bands: 1-3, 4-7, 8-14, 15+."""
    for index, upper in enumerate((3, 7, 14)):
        if days_overdue <= upper:
            return index
    return 3


# --- the open overdue loans --------------------------------------------------------------------


# (overdue by, replacement value in paise, expected late days, expected fee in paise)
OVERDUE_LOANS = [
    (SECOND, 650_000, 1, 1_000),
    (3 * DAY, 650_000, 3, 3_000),
    (3 * DAY + SECOND, 650_000, 4, 4_000),
    (7 * DAY, 650_000, 7, 7_000),
    (7 * DAY + SECOND, 650_000, 8, 8_000),
    (14 * DAY, 650_000, 14, 14_000),
    (14 * DAY + SECOND, 650_000, 15, 15_000),
    (30 * DAY, 650_000, 30, 20_000),  # the per-loan cap of ₹200
    (30 * DAY, 15_000, 30, 15_000),  # the replacement value (₹150) is lower than the cap
]


@pytest.fixture
def overdue_library(session_factory):
    """One loan per row of OVERDUE_LOANS plus one due exactly now. The two 30-day loans share a
    member; every other loan has its own."""
    shared = new_member(session_factory, name="Shared Member")
    for number, (late_by, value, _, _) in enumerate(OVERDUE_LOANS):
        if number >= len(OVERDUE_LOANS) - 2:
            member = shared
        else:
            member = new_member(session_factory, name=f"Member {number}")
        item = new_item(session_factory, name=f"Item {number}", replacement_value_paise=value)
        checked_out_loan(session_factory, member, item, NOW - late_by)
    on_time = new_item(session_factory, name="Due exactly now")
    checked_out_loan(session_factory, new_member(session_factory, name="On time"), on_time, NOW)
    return shared


def test_each_overdue_loan_lands_in_its_band_at_the_exact_boundaries(api, overdue_library):
    open_ = fetch(api, "overdue-aging")["open"]

    assert [(b["count"], b["accrued_fee_paise"]) for b in open_["bands"]] == [
        (2, 4_000),  # 1s late and exactly 3 days late
        (2, 11_000),  # 3 days + 1s and exactly 7 days
        (2, 22_000),  # 7 days + 1s and exactly 14 days
        (3, 50_000),  # 14 days + 1s, and two 30-day loans (₹200 cap and ₹150 replacement cap)
    ]
    assert open_["count"] == 9  # the loan due exactly now is not overdue
    assert open_["accrued_fee_paise"] == 87_000
    assert open_["oldest_days_overdue"] == 30
    # Only the loans overdue by MORE than 14 days block their member: exactly 14 days does not.
    assert open_["blocking_count"] == 3
    assert [(b["min_days"], b["max_days"]) for b in open_["bands"]] == [
        (band.min_days, band.max_days) for band in AGING_BANDS
    ]


def test_the_bands_always_add_up_to_the_totals(api, overdue_library):
    open_ = fetch(api, "overdue-aging")["open"]

    assert sum(b["count"] for b in open_["bands"]) == open_["count"]
    assert sum(b["accrued_fee_paise"] for b in open_["bands"]) == open_["accrued_fee_paise"]


def test_the_aging_agrees_with_the_overdue_loans_endpoint_row_by_row(api, overdue_library):
    rows = api.get("/loans/overdue?limit=200", at=NOW).json()
    open_ = fetch(api, "overdue-aging")["open"]

    expected_counts = [0, 0, 0, 0]
    expected_fees = [0, 0, 0, 0]
    for row in rows["results"]:
        band = band_of(row["days_overdue"])
        expected_counts[band] += 1
        expected_fees[band] += row["fee_if_returned_now_paise"]
    assert rows["total"] == open_["count"] == 9
    assert [b["count"] for b in open_["bands"]] == expected_counts
    assert [b["accrued_fee_paise"] for b in open_["bands"]] == expected_fees
    assert open_["accrued_fee_paise"] == sum(
        r["fee_if_returned_now_paise"] for r in rows["results"]
    )
    assert open_["oldest_days_overdue"] == rows["results"][0]["days_overdue"]
    assert open_["blocking_count"] == sum(1 for r in rows["results"] if r["days_overdue"] > 14)


def test_top_members_are_summed_per_member_and_ranked_by_fee(api, overdue_library):
    top = fetch(api, "overdue-aging")["top_members"]

    assert [
        (m["member_name"], m["loans"], m["longest_days_overdue"], m["accrued_fee_paise"])
        for m in top
    ] == [
        ("Shared Member", 2, 30, 35_000),  # ₹200 + ₹150
        ("Member 6", 1, 15, 15_000),
        ("Member 5", 1, 14, 14_000),
        ("Member 4", 1, 8, 8_000),
        ("Member 3", 1, 7, 7_000),
    ]
    assert len(top) == 5  # the list is cut at five members


def test_members_with_equal_fees_are_ordered_by_days_then_id(api, session_factory):
    first = new_member(session_factory, name="First")
    second = new_member(session_factory, name="Second")
    third = new_member(session_factory, name="Third")
    # Each is charged ₹100 (10 days at ₹10) except the third, who has 5 days: ₹50.
    for member, late_days in ((second, 10), (first, 10), (third, 5)):
        item = new_item(session_factory, name=f"Item of {member}")
        checked_out_loan(session_factory, member, item, NOW - late_days * DAY)

    top = fetch(api, "overdue-aging")["top_members"]

    assert [m["member_name"] for m in top] == ["First", "Second", "Third"]


@pytest.mark.parametrize(
    ("late_by", "days", "fee", "band", "blocking"),
    [
        (timedelta(0), 0, 0, None, 0),
        (SECOND, 1, 1_000, 0, 0),
        (3 * DAY, 3, 3_000, 0, 0),
        (3 * DAY + SECOND, 4, 4_000, 1, 0),
        (7 * DAY, 7, 7_000, 1, 0),
        (7 * DAY + SECOND, 8, 8_000, 2, 0),
        (14 * DAY, 14, 14_000, 2, 0),
        (14 * DAY + SECOND, 15, 15_000, 3, 1),
        (30 * DAY, 30, 20_000, 3, 1),
    ],
)
def test_moving_the_test_clock_moves_a_loan_through_the_bands(
    api, late_by, days, fee, band, blocking
):
    member = api.make_member()
    item = api.make_item()
    api.rent(item["id"], member["id"])
    due = NOW + timedelta(days=7)

    open_ = fetch(api, "overdue-aging", at=due + late_by)["open"]

    assert open_["count"] == (0 if band is None else 1)
    assert open_["accrued_fee_paise"] == fee
    assert open_["blocking_count"] == blocking
    assert open_["oldest_days_overdue"] == (None if band is None else days)
    assert [b["count"] for b in open_["bands"]] == [1 if i == band else 0 for i in range(4)]


def test_a_loan_that_is_not_yet_due_is_not_in_any_band(api):
    api.rent(api.make_item()["id"], api.make_member()["id"])

    open_ = fetch(api, "overdue-aging", at=NOW + 7 * DAY - SECOND)["open"]

    assert open_["count"] == 0 and open_["oldest_days_overdue"] is None


def test_reservations_and_returned_loans_are_never_overdue(api, session_factory):
    member = new_member(session_factory)
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - 20 * DAY,
        returned_at=NOW - 5 * DAY,
    )
    assert api.reserve(new_item(session_factory, name="Held"), member).status_code == 201

    assert fetch(api, "overdue-aging", at=NOW + 30 * DAY)["open"]["count"] == 0


# --- loans returned in the period --------------------------------------------------------------


@pytest.fixture
def returns_library(session_factory):
    """Returned loans around the edges of the 7-day report, of the matching point a week earlier
    (NOW minus 7 days), and of the future."""
    member = new_member(session_factory, name="Returner")
    item = new_item(session_factory)

    def give_back(returned_at, *, late_by=timedelta(0), fee_paise=0):
        returned_loan(
            session_factory,
            member,
            item,
            due_at=returned_at - late_by,
            returned_at=returned_at,
            fee_paise=fee_paise,
        )

    give_back(CURRENT_START)  # first instant of the report, on time
    give_back(CURRENT_START - MICRO, late_by=DAY, fee_paise=6_000)  # late in the previous week
    give_back(NOW - 7 * DAY, late_by=DAY, fee_paise=2_000)  # the matching instant a week ago
    give_back(NOW - 7 * DAY + MICRO, late_by=DAY, fee_paise=9_000)  # a moment later: not matched
    give_back(NOW, late_by=2 * DAY + SECOND, fee_paise=3_000)  # exactly now: late by 3 days
    give_back(NOW - DAY, late_by=SECOND, fee_paise=1_000)  # one second late counts as a day
    give_back(NOW + SECOND, late_by=DAY, fee_paise=5_000)  # in the future: not yet happened
    give_back(PREVIOUS_START)  # first instant of the previous week, on time
    give_back(PREVIOUS_START - MICRO, late_by=DAY, fee_paise=7_000)  # before both periods


def test_late_returns_count_only_the_loans_returned_inside_the_period(api, returns_library):
    returns = fetch(api, "overdue-aging", days=7)["returns"]

    assert returns == {
        "returned": 3,  # CURRENT_START, NOW - 1 day, NOW
        "late": 2,
        "late_rate_pct": 66.7,
        "average_days_late": 2.0,  # (3 + 1) late days over 2 late returns
        "fees_charged_paise": 4_000,
    }


def test_the_summary_compares_returns_with_the_period_before(api, returns_library):
    summary = fetch(api, "summary", days=7)

    # The previous week counts up to NOW - 7 days: the first return and the one at that very
    # instant, not the two later ones (which would make last week look busier than it was so far).
    assert summary["returns"] == {"current": 3, "previous": 2, "change_pct": 50.0}
    assert summary["late_return_rate"] == {"current_pct": 66.7, "previous_pct": 50.0}
    assert summary["fees_charged_paise"] == {
        "current": 4_000,
        "previous": 2_000,
        "change_pct": 100.0,
    }


def test_a_return_exactly_at_the_due_time_is_on_time_and_one_second_after_is_late(
    api, session_factory
):
    member = new_member(session_factory)
    item = new_item(session_factory)
    returned_loan(session_factory, member, item, due_at=NOW - HOUR, returned_at=NOW - HOUR)
    returned_loan(
        session_factory,
        member,
        item,
        due_at=NOW - HOUR,
        returned_at=NOW - HOUR + SECOND,
        fee_paise=1_000,
    )

    returns = fetch(api, "overdue-aging", days=1)["returns"]

    assert (returns["returned"], returns["late"], returns["average_days_late"]) == (2, 1, 1.0)


def test_late_return_fees_equal_what_the_return_endpoint_charged(api):
    member = api.make_member()
    item = api.make_item()
    loan = api.rent(item["id"], member["id"])
    due = NOW + 7 * DAY
    charged = api.return_late(item["id"], due, 4 * DAY + SECOND)["fee_charged_paise"]
    assert charged == 5_000 and loan["status"] == "checked_out"

    at = due + 5 * DAY
    returns = fetch(api, "overdue-aging", at=at, days=7)["returns"]
    summary = fetch(api, "summary", at=at, days=7)

    assert returns["fees_charged_paise"] == charged
    assert returns["average_days_late"] == 5.0
    assert summary["fees_charged_paise"]["current"] == charged
    statement = api.get(f"/members/{member['id']}/statement", at=at).json()
    assert statement["total_fees_paise"] == charged
