"""GET /analytics/summary: fleet, loans, members, activity and agreement with other routes."""

from datetime import timedelta

import pytest

from app.domain.enums import ItemStatus, LoanStatus, MemberStatus
from tests.api.analytics_helpers import (
    api_member_view,
    checked_out_loan,
    fetch,
    new_item,
    new_member,
    payment,
    reservation,
    returned_loan,
    suspended_member,
)
from tests.builders import NOW

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
SECOND = timedelta(seconds=1)
MICRO = timedelta(microseconds=1)
HOLD = timedelta(hours=48)
# 12 Oct 2026 15:30 IST. A 7-day report is 6 Oct 00:00 IST up to 13 Oct 00:00 IST, the week before
# that is 29 Sep 00:00 IST up to 6 Oct 00:00 IST.
CURRENT_START = NOW.replace(hour=0, minute=0) - timedelta(days=6) - timedelta(hours=5, minutes=30)
PREVIOUS_START = CURRENT_START - 7 * DAY
MATCHING_POINT = NOW - 7 * DAY  # how far last week is compared: the same point in its week


def listed(api, status: str, at=NOW) -> int:
    response = api.get(f"/items?status={status}&limit=200", at=at)
    assert response.status_code == 200, response.text
    return response.json()["total"]


# --- the fleet and the loans right now ---------------------------------------------------------


@pytest.fixture
def mixed_library(session_factory):
    """Eight items in every state a reader might trip over; each loan belongs to its own member."""

    def holder(name):
        return new_member(session_factory, name=name)

    new_item(session_factory, name="Idle")
    lapsed = new_item(session_factory, name="Lapsed hold")
    reservation(session_factory, holder("Lapsed"), lapsed, NOW - HOLD - SECOND)
    fresh = new_item(session_factory, name="Fresh hold")
    reservation(session_factory, holder("Fresh"), fresh, NOW - HOUR)
    on_time = new_item(session_factory, name="On time")
    checked_out_loan(session_factory, holder("On time"), on_time, NOW + 3 * DAY)
    late = new_item(session_factory, name="Late")
    checked_out_loan(session_factory, holder("Late"), late, NOW - 3 * DAY)
    very_late = new_item(session_factory, name="Very late")
    checked_out_loan(session_factory, holder("Very late"), very_late, NOW - 16 * DAY)
    new_item(session_factory, name="Broken", status=ItemStatus.UNDER_MAINTENANCE)
    pulled = new_item(session_factory, name="Pulled while out")
    checked_out_loan(
        session_factory,
        holder("Pulled"),
        pulled,
        NOW - 2 * DAY,
        item_status=ItemStatus.UNDER_MAINTENANCE,
    )


def test_the_fleet_mix_is_the_mix_the_items_endpoint_reports(api, mixed_library):
    fleet = fetch(api, "summary")["fleet"]

    assert fleet == {
        "total_items": 8,
        "available": 2,  # the idle item and the one whose 48-hour hold ran out
        "reserved": 1,
        "checked_out": 1,
        "overdue": 2,
        "under_maintenance": 2,
    }
    assert fleet["total_items"] == api.get("/items?limit=200").json()["total"]
    for key, status in [
        ("available", "available"),
        ("reserved", "reserved"),
        ("checked_out", "checked_out"),
        ("overdue", "overdue"),
        ("under_maintenance", "under_maintenance"),
    ]:
        assert fleet[key] == listed(api, status), key


def test_loans_now_count_only_holds_that_have_not_lapsed(api, mixed_library):
    loans = fetch(api, "summary")["loans"]

    assert loans == {
        "active": 5,  # one fresh hold and four checked-out loans, the lapsed hold excluded
        "reserved": 1,
        "checked_out": 4,
        "overdue": 3,  # includes the loan on the item pulled for maintenance
        "overdue_share_pct": 75.0,
    }
    assert loans["overdue"] == api.get("/loans/overdue?limit=200").json()["total"]


def test_active_loans_equal_the_sum_of_every_members_active_loan_count(api, mixed_library):
    members = api.get("/members?limit=200").json()["results"]

    held = sum(api_member_view(api, member["id"])["active_loan_count"] for member in members)

    assert held == fetch(api, "summary")["loans"]["active"]


@pytest.mark.parametrize(
    ("moment", "reserved", "available"),
    [(NOW + HOLD - SECOND, 1, 0), (NOW + HOLD, None, None), (NOW + HOLD + SECOND, 0, 1)],
)
def test_a_hold_lapses_in_the_report_exactly_when_the_item_endpoint_says_so(
    api, moment, reserved, available
):
    item = api.make_item()
    assert api.reserve(item["id"], api.make_member()["id"]).status_code == 201

    fleet = fetch(api, "summary", at=moment)["fleet"]
    loans = fetch(api, "summary", at=moment)["loans"]

    status = api.get(f"/items/{item['id']}", at=moment).json()["status"]
    assert fleet["reserved"] == (1 if status == "reserved" else 0)
    assert fleet["available"] == (1 if status == "available" else 0)
    assert loans["reserved"] == loans["active"] == fleet["reserved"]
    if reserved is not None:  # the instants either side of the boundary are fixed by the rules
        assert (fleet["reserved"], fleet["available"]) == (reserved, available)


def test_an_item_goes_from_checked_out_to_overdue_exactly_after_its_due_time(api):
    api.rent(api.make_item()["id"], api.make_member()["id"])
    due = NOW + 7 * DAY

    at_due = fetch(api, "summary", at=due)
    just_after = fetch(api, "summary", at=due + SECOND)

    assert (at_due["fleet"]["checked_out"], at_due["fleet"]["overdue"]) == (1, 0)
    assert (just_after["fleet"]["checked_out"], just_after["fleet"]["overdue"]) == (0, 1)
    assert (at_due["loans"]["overdue"], just_after["loans"]["overdue"]) == (0, 1)
    assert just_after["loans"]["overdue_share_pct"] == 100.0


# --- members and receivables -------------------------------------------------------------------


@pytest.fixture
def ledger_library(session_factory):
    """Seven members covering both sides of every blocking boundary. Returns their ids by name."""

    def with_balance(member, fee_paise, paid_paise=0):
        returned_loan(
            session_factory,
            member,
            new_item(session_factory),
            due_at=NOW - 100 * DAY,
            returned_at=NOW - 99 * DAY,
            fee_paise=fee_paise,
        )
        if paid_paise:
            payment(session_factory, member, NOW - 98 * DAY, paid_paise)

    ids = {}
    ids["clear"] = new_member(session_factory, name="Clear")
    ids["limit"] = new_member(session_factory, name="Exactly ₹100")
    with_balance(ids["limit"], 10_000)
    ids["over"] = new_member(session_factory, name="₹100.01")
    with_balance(ids["over"], 10_001)
    ids["suspended"] = suspended_member(session_factory, name="Suspended")
    ids["both"] = suspended_member(session_factory, name="Suspended and owing")
    with_balance(ids["both"], 25_000, 5_000)
    ids["fourteen"] = new_member(session_factory, name="Overdue 14 days")
    checked_out_loan(session_factory, ids["fourteen"], new_item(session_factory), NOW - 14 * DAY)
    ids["fifteen"] = new_member(session_factory, name="Overdue 14 days and a second")
    checked_out_loan(
        session_factory, ids["fifteen"], new_item(session_factory), NOW - 14 * DAY - SECOND
    )
    return ids


def test_members_are_blocked_for_the_same_reasons_the_member_endpoint_gives(api, ledger_library):
    members = fetch(api, "summary")["members"]

    assert members == {
        "total": 7,
        "active": 5,
        "suspended": 2,
        "blocked": 4,  # over ₹100, suspended, suspended and owing, overdue past 14 days
        "blocked_suspended": 2,
        "blocked_unpaid_fees": 2,
        "blocked_long_overdue": 1,
    }
    views = [api_member_view(api, member_id) for member_id in ledger_library.values()]
    assert members["blocked"] == sum(1 for view in views if view["block_reasons"])
    for key, reason in [
        ("blocked_suspended", "suspended"),
        ("blocked_unpaid_fees", "unpaid_fees"),
        ("blocked_long_overdue", "long_overdue"),
    ]:
        assert members[key] == sum(1 for view in views if reason in view["block_reasons"]), key
    assert members["suspended"] == sum(1 for v in views if v["status"] == MemberStatus.SUSPENDED)


def test_receivables_add_up_to_the_member_balances(api, ledger_library):
    receivables = fetch(api, "summary")["receivables"]
    balances = [
        api_member_view(api, member_id)["balance_paise"] for member_id in ledger_library.values()
    ]

    assert receivables == {
        "outstanding_paise": 40_001,  # 10,000 + 10,001 + 20,000
        "unapplied_credit_paise": 0,
        "members_with_balance": 3,
        "members_over_limit": 2,  # exactly ₹100 is not over the limit
    }
    assert receivables["outstanding_paise"] == sum(b for b in balances if b > 0)
    assert receivables["members_with_balance"] == sum(1 for b in balances if b > 0)
    assert receivables["members_over_limit"] == sum(1 for b in balances if b > 10_000)


def test_a_credit_balance_is_counted_apart_and_never_reduces_what_others_owe(api, session_factory):
    owes = new_member(session_factory, name="Owes")
    returned_loan(
        session_factory,
        owes,
        new_item(session_factory),
        due_at=NOW - 10 * DAY,
        returned_at=NOW - 9 * DAY,
        fee_paise=3_000,
    )
    credit = new_member(session_factory, name="Credit")
    payment(session_factory, credit, NOW - DAY, 2_000)

    receivables = fetch(api, "summary")["receivables"]

    assert receivables == {
        "outstanding_paise": 3_000,  # what Owes owes; the credit is not netted off
        "unapplied_credit_paise": 2_000,
        "members_with_balance": 1,
        "members_over_limit": 0,
    }
    assert api_member_view(api, credit)["balance_paise"] == -2_000
    assert api_member_view(api, owes)["balance_paise"] == 3_000


def test_with_only_credit_nothing_is_outstanding_and_the_total_is_not_negative(
    api, session_factory
):
    payment(session_factory, new_member(session_factory), NOW - DAY, 2_000)

    receivables = fetch(api, "summary")["receivables"]

    assert receivables["outstanding_paise"] == 0
    assert receivables["unapplied_credit_paise"] == 2_000
    assert receivables["members_with_balance"] == 0


def test_a_member_becomes_blocked_as_the_clock_passes_14_days(api, session_factory):
    member = new_member(session_factory)
    checked_out_loan(session_factory, member, new_item(session_factory), NOW)

    before = fetch(api, "summary", at=NOW + 14 * DAY)["members"]
    after = fetch(api, "summary", at=NOW + 14 * DAY + SECOND)["members"]

    assert (before["blocked"], before["blocked_long_overdue"]) == (0, 0)
    assert (after["blocked"], after["blocked_long_overdue"]) == (1, 1)
    view = api_member_view(api, member, at=NOW + 14 * DAY + SECOND)
    assert view["block_reasons"] == ["long_overdue"]


# --- activity in the period ---------------------------------------------------------------------


def test_reservations_are_counted_by_the_ist_period_they_were_made_in(api, session_factory):
    member = new_member(session_factory)
    times = [
        (CURRENT_START, LoanStatus.RESERVED),
        (NOW - HOUR, LoanStatus.CANCELLED),  # cancelled holds were still made
        (NOW, LoanStatus.RESERVED),
        (NOW + SECOND, LoanStatus.RESERVED),  # not made yet
        (PREVIOUS_START, LoanStatus.RESERVED),
        (MATCHING_POINT, LoanStatus.CANCELLED),  # the same point a week ago: compared
        (MATCHING_POINT + MICRO, LoanStatus.RESERVED),  # a moment later: not compared yet
        (CURRENT_START - MICRO, LoanStatus.RESERVED),  # end of last week: not compared yet
        (PREVIOUS_START - MICRO, LoanStatus.RESERVED),  # before both periods
    ]
    for number, (moment, status) in enumerate(times):
        item = new_item(session_factory, name=f"Item {number}")
        reservation(session_factory, member, item, moment, status)

    reservations = fetch(api, "summary", days=7)["reservations_created"]

    assert reservations == {"current": 3, "previous": 2, "change_pct": 50.0}


def test_checkouts_are_counted_by_the_ist_period_they_happened_in(api, session_factory):
    member = new_member(session_factory)
    item = new_item(session_factory)
    for moment in [
        CURRENT_START,
        CURRENT_START - MICRO,
        NOW - HOUR,
        NOW,
        NOW + SECOND,
        PREVIOUS_START,
        MATCHING_POINT,
        MATCHING_POINT + MICRO,
        PREVIOUS_START - MICRO,
    ]:
        returned_loan(
            session_factory,
            member,
            item,
            due_at=moment + 7 * DAY,
            returned_at=moment + 7 * DAY,
            checked_out_at=moment,
        )

    checkouts = fetch(api, "summary", days=7)["checkouts"]

    assert checkouts == {"current": 3, "previous": 2, "change_pct": 50.0}


def test_activity_made_through_the_api_shows_up_in_the_report(api):
    member = api.make_member()
    item = api.make_item()
    api.rent(item["id"], member["id"])
    api.return_late(item["id"], NOW + 7 * DAY, 2 * DAY)
    later = NOW + 9 * DAY

    summary = fetch(api, "summary", at=later, days=1)
    wide = fetch(api, "summary", at=later, days=30)

    assert summary["returns"]["current"] == 1
    assert summary["checkouts"]["current"] == 0  # the checkout was nine days earlier
    assert wide["reservations_created"]["current"] == 1
    assert wide["checkouts"]["current"] == 1
    assert wide["fees_charged_paise"]["current"] == 2_000
    assert wide["late_return_rate"]["current_pct"] == 100.0


def test_a_report_for_a_long_ago_clock_sees_only_what_had_happened_by_then(api, session_factory):
    member = new_member(session_factory)
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - DAY,
        returned_at=NOW,
        fee_paise=1_000,
    )

    before = fetch(api, "summary", at=NOW - SECOND, days=7)
    after = fetch(api, "summary", at=NOW, days=7)

    assert before["returns"]["current"] == 0 and before["fees_charged_paise"]["current"] == 0
    assert after["returns"]["current"] == 1 and after["fees_charged_paise"]["current"] == 1_000


# --- fleet "overdue" is about items, loans "overdue" about loans -------------------------------


def maintenance_items_on_a_late_loan(api) -> list[int]:
    late = api.get("/loans/overdue?limit=200").json()["results"]
    return [
        row["item_id"]
        for row in late
        if api.get(f"/items/{row['item_id']}").json()["status"] == "under_maintenance"
    ]


def test_loans_overdue_exceeds_fleet_overdue_by_the_late_loans_on_items_in_maintenance(
    api, mixed_library
):
    summary = fetch(api, "summary")
    pulled = maintenance_items_on_a_late_loan(api)

    assert len(pulled) == 1  # the item pulled for maintenance while it was out and late
    assert summary["fleet"]["overdue"] == listed(api, "overdue") == 2
    assert summary["loans"]["overdue"] == api.get("/loans/overdue").json()["total"] == 3
    assert summary["loans"]["overdue"] - summary["fleet"]["overdue"] == len(pulled)
    # The item is counted once in the fleet, under maintenance, and its loan is still a loan.
    assert summary["fleet"]["under_maintenance"] == listed(api, "under_maintenance") == 2
    fleet = summary["fleet"]
    assert sum(fleet[key] for key in fleet if key != "total_items") == fleet["total_items"]
    assert summary["loans"]["checked_out"] == 4  # all four loans, the pulled item's included


def test_without_maintenance_fleet_overdue_and_loans_overdue_are_equal(api, session_factory):
    for number, late_by in enumerate((DAY, 5 * DAY)):
        member = new_member(session_factory, name=f"Late {number}")
        item = new_item(session_factory, name=f"Late item {number}")
        checked_out_loan(session_factory, member, item, NOW - late_by)

    summary = fetch(api, "summary")

    assert summary["fleet"]["overdue"] == summary["loans"]["overdue"] == 2
    assert maintenance_items_on_a_late_loan(api) == []


def test_the_openapi_documents_the_difference_between_the_two_overdue_counts(api):
    schemas = api.get("/openapi.json").json()["components"]["schemas"]

    fleet_overdue = schemas["FleetRead"]["properties"]["overdue"]["description"]
    loans_overdue = schemas["LoansNowRead"]["properties"]["overdue"]["description"]
    assert "not under maintenance" in fleet_overdue and "loans.overdue" in fleet_overdue
    assert "maintenance" in loans_overdue and "checked_out" in loans_overdue
    assert "/loans/overdue" in schemas["LoansNowRead"]["description"]
    assert "/items?status=" in schemas["FleetRead"]["description"]


# --- a clock earlier than the data: current rows, judged at that clock --------------------------


@pytest.fixture
def library_seen_from_the_past(session_factory):
    """Rows that all happen after `PAST`: a loan checked out after it, a loan that comes back
    later, a hold made after it and a member who joins long after it."""
    keen = new_member(session_factory, name="Joins later", join_date=(NOW + 30 * DAY).date())
    out = new_item(session_factory, name="Out")
    checked_out_loan(session_factory, keen, out, NOW + 7 * DAY)  # checked out at NOW
    regular = new_member(session_factory, name="Regular")
    back = new_item(session_factory, name="Back")
    returned_loan(
        session_factory, regular, back, due_at=NOW + 5 * DAY, returned_at=NOW - DAY
    )  # out from NOW - 2 days, returned a day ago
    held = new_item(session_factory, name="Held")
    reservation(session_factory, regular, held, NOW - HOUR)
    return NOW - 3 * DAY


def test_under_a_backward_clock_fleet_loan_and_member_counts_describe_the_current_rows(
    api, library_seen_from_the_past
):
    past = library_seen_from_the_past

    summary = fetch(api, "summary", at=past, days=7)

    # Judged at `past`, the rows as they are now: the loan that is out, the hold (not yet lapsed
    # at that clock) and the member who has not joined yet are all counted.
    assert summary["fleet"] == {
        "total_items": 3,
        "available": 1,  # "Back": it is shown as returned, not as the loan it was at that time
        "reserved": 1,
        "checked_out": 1,
        "overdue": 0,
        "under_maintenance": 0,
    }
    assert summary["loans"] == {
        "active": 2,
        "reserved": 1,
        "checked_out": 1,
        "overdue": 0,
        "overdue_share_pct": 0.0,
    }
    assert summary["members"]["total"] == 2
    # Activity is different: nothing dated after the clock has happened yet.
    for key in ("reservations_created", "checkouts", "returns"):
        assert summary[key]["current"] == 0, key


def test_under_a_backward_clock_the_counts_still_agree_with_the_existing_endpoints(
    api, library_seen_from_the_past
):
    past = library_seen_from_the_past
    fleet = fetch(api, "summary", at=past)["fleet"]
    loans = fetch(api, "summary", at=past)["loans"]

    for key in ("available", "reserved", "checked_out", "overdue", "under_maintenance"):
        assert fleet[key] == listed(api, key, at=past), key
    members = api.get("/members?limit=200", at=past).json()
    assert fetch(api, "summary", at=past)["members"]["total"] == members["total"]
    held = sum(
        api_member_view(api, member["id"], at=past)["active_loan_count"]
        for member in members["results"]
    )
    assert loans["active"] == held
    assert loans["overdue"] == api.get("/loans/overdue", at=past).json()["total"]


def test_the_same_rows_give_different_activity_but_the_period_figures_follow_the_clock(
    api, library_seen_from_the_past
):
    now = fetch(api, "summary", days=7)

    assert now["fleet"]["total_items"] == 3 and now["members"]["total"] == 2
    assert now["reservations_created"]["current"] == 3  # the hold, the loan out, the returned loan
    assert now["checkouts"]["current"] == 2  # the returned loan (2 days ago) and the loan out now
    assert now["returns"]["current"] == 1
