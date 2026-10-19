"""GET /analytics/payments, plus the guarantees that apply to every analytics report."""

import re
from datetime import timedelta

import pytest

from app.seed import seed_database
from tests.api.analytics_helpers import (
    api_member_view,
    api_statement,
    captured_sql,
    checked_out_loan,
    fetch,
    new_item,
    new_member,
    payment,
    reservation,
    returned_loan,
    run,
    snapshot,
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
ENDPOINTS = ["summary", "overdue-aging", "payments", "utilization", "demand"]


# --- money received -----------------------------------------------------------------------------


@pytest.fixture
def payments_library(session_factory):
    """Payments on both sides of every edge of the 7-day report. Returns the paying member's id."""
    member = new_member(session_factory, name="Payer")
    for moment, paise in [
        (CURRENT_START, 1_000),  # first instant of the report: Tue 6 Oct 00:00 IST
        (CURRENT_START - MICRO, 2_000),  # end of last week: not compared yet (today is half over)
        (MATCHING_POINT, 5_000),  # the same point last week: the last instant compared
        (MATCHING_POINT + MICRO, 6_000),  # a moment later: not compared yet
        (PREVIOUS_START, 3_000),  # first instant of the previous period
        (PREVIOUS_START - MICRO, 4_000),  # before both periods: counted nowhere
        (NOW.replace(day=8, hour=18, minute=29, second=59, microsecond=999_999), 100),  # 8 Oct IST
        (NOW.replace(day=8, hour=18, minute=30, second=0, microsecond=0), 200),  # 9 Oct 00:00 IST
        (NOW, 500),  # exactly now
        (NOW + SECOND, 7_000),  # later today, not received yet
        (NOW.replace(day=12, hour=18, minute=30), 9_000),  # 13 Oct 00:00 IST, tomorrow
    ]:
        payment(session_factory, member, moment, paise)
    return member


def test_payments_are_totalled_per_period_with_both_edges_exact(api, payments_library):
    data = fetch(api, "payments", days=7)

    assert data["collected"] == {"current": 1_800, "previous": 8_000, "change_pct": -77.5}
    assert data["payments"] == {"current": 4, "previous": 2, "change_pct": 100.0}
    assert data["average_payment_paise"] == 450


def test_daily_buckets_split_at_ist_midnight(api, payments_library):
    series = fetch(api, "payments", days=7)["series"]

    assert [(slot["start"], slot["collected_paise"], slot["count"]) for slot in series] == [
        ("2026-10-06", 1_000, 1),
        ("2026-10-07", 0, 0),
        ("2026-10-08", 100, 1),  # 23:59:59.999999 IST
        ("2026-10-09", 200, 1),  # 00:00:00 IST
        ("2026-10-10", 0, 0),
        ("2026-10-11", 0, 0),
        ("2026-10-12", 500, 1),  # the payment made one second after now is not counted
    ]


def test_weekly_buckets_start_on_monday(api, payments_library):
    series = fetch(api, "payments", days=7, bucket="week")["series"]

    assert [(slot["start"], slot["collected_paise"], slot["count"]) for slot in series] == [
        ("2026-10-05", 1_300, 3),  # Mon 5 Oct: the report's first six days
        ("2026-10-12", 500, 1),
    ]


@pytest.mark.parametrize("bucket", ["day", "week"])
def test_the_series_adds_up_to_the_collected_total(api, payments_library, bucket):
    data = fetch(api, "payments", days=7, bucket=bucket)

    assert sum(slot["collected_paise"] for slot in data["series"]) == data["collected"]["current"]
    assert sum(slot["count"] for slot in data["series"]) == data["payments"]["current"]
    assert data["bucket"] == bucket


def test_the_summary_reports_the_same_collection_figures(api, payments_library):
    summary = fetch(api, "summary", days=7)["payments_collected_paise"]

    assert summary == fetch(api, "payments", days=7)["collected"]


def test_moving_the_clock_forward_brings_later_payments_into_view(api, payments_library):
    before = fetch(api, "payments", at=NOW, days=1)
    after = fetch(api, "payments", at=NOW + SECOND, days=1)

    # Today (12 Oct IST) holds the 500 made at NOW; the 7,000 made a second later is not here yet.
    assert before["collected"]["current"] == 500
    assert after["collected"]["current"] == 7_500
    # The 9,000 dated 13 Oct 00:00 IST is tomorrow and stays out of both.


def test_collected_against_charged_uses_the_fees_charged_in_the_same_period(api, session_factory):
    member = new_member(session_factory)
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - 3 * DAY,
        returned_at=NOW - DAY,
        fee_paise=4_000,
    )
    payment(session_factory, member, NOW - HOUR, 6_000)  # more than this period's fees

    data = fetch(api, "payments", days=7)

    assert data["fees_charged_paise"] == {"current": 4_000, "previous": 0, "change_pct": None}
    assert data["collected_to_charged_pct"] == 150.0


def test_a_fee_and_payment_made_through_the_api_appear_straight_away(api):
    member = api.make_member()
    item = api.make_item()
    api.rent(item["id"], member["id"])
    due = NOW + 7 * DAY
    assert api.return_late(item["id"], due, 4 * DAY + SECOND)["fee_charged_paise"] == 5_000
    paid_at = due + 4 * DAY + 2 * SECOND
    path = f"/members/{member['id']}/payments"
    assert api.post(path, json={"amount_paise": 2_550}, at=paid_at).status_code == 201

    data = fetch(api, "payments", at=paid_at)

    assert data["collected"]["current"] == 2_550
    assert data["fees_charged_paise"]["current"] == 5_000
    assert data["collected_to_charged_pct"] == 51.0
    assert data["series"][-1]["collected_paise"] == 2_550
    assert data["average_payment_paise"] == 2_550
    assert data["ledger"] == {
        "fees_charged_paise": 5_000,
        "collected_paise": 2_550,
        "outstanding_paise": 2_450,
        "unapplied_credit_paise": 0,
        "members_with_balance": 1,
        "members_over_limit": 0,
    }
    assert data["top_balances"] == [
        {"member_id": member["id"], "member_name": member["name"], "balance_paise": 2_450}
    ]


def test_the_average_payment_is_whole_paise_rounded_half_up(api, session_factory):
    member = new_member(session_factory)
    for paise in (100, 101):
        payment(session_factory, member, NOW - HOUR, paise)

    assert fetch(api, "payments")["average_payment_paise"] == 101  # 100.5


# --- the ledger and the balances ---------------------------------------------------------------


@pytest.fixture
def balances_library(session_factory):
    """Six members owing money (20,000 down to 100 paise), one settled and one in credit."""
    owed = {}

    def member_owing(name, fee_paise, paid_paise=0):
        member = new_member(session_factory, name=name)
        if fee_paise:
            returned_loan(
                session_factory,
                member,
                new_item(session_factory),
                due_at=NOW - 200 * DAY,
                returned_at=NOW - 199 * DAY,
                fee_paise=fee_paise,
            )
        if paid_paise:
            payment(session_factory, member, NOW - 150 * DAY, paid_paise)
        owed[name] = member

    member_owing("Big", 25_000, 5_000)
    member_owing("Limit", 10_000)
    member_owing("Over", 10_001)
    member_owing("Settled", 3_000, 3_000)
    member_owing("Credit", 0, 2_000)
    member_owing("Tie B", 200)
    member_owing("Tie A", 200)
    member_owing("Small", 100)
    return owed


def test_the_ledger_totals_equal_the_sums_of_the_member_statements(api, balances_library):
    ledger = fetch(api, "payments")["ledger"]
    statements = [api_statement(api, member_id) for member_id in balances_library.values()]

    assert ledger == {
        "fees_charged_paise": 48_501,
        "collected_paise": 10_000,
        "outstanding_paise": 40_501,  # the six balances above zero
        "unapplied_credit_paise": 2_000,  # Credit paid ₹20 ahead
        "members_with_balance": 6,  # not Settled and not Credit
        "members_over_limit": 2,  # Big and Over; exactly ₹100 is not over
    }
    balances = [s["balance_paise"] for s in statements]
    assert ledger["fees_charged_paise"] == sum(s["total_fees_paise"] for s in statements)
    assert ledger["collected_paise"] == sum(s["total_payments_paise"] for s in statements)
    assert ledger["outstanding_paise"] == sum(b for b in balances if b > 0)
    assert ledger["unapplied_credit_paise"] == -sum(b for b in balances if b < 0)
    # The views of the money tell one story: net = owed - credit.
    assert ledger["fees_charged_paise"] - ledger["collected_paise"] == sum(balances)
    assert sum(balances) == ledger["outstanding_paise"] - ledger["unapplied_credit_paise"]


def test_the_top_balances_are_the_biggest_five_and_ties_go_to_the_older_member(
    api, balances_library
):
    top = fetch(api, "payments")["top_balances"]

    assert [(m["member_name"], m["balance_paise"]) for m in top] == [
        ("Big", 20_000),
        ("Over", 10_001),
        ("Limit", 10_000),
        ("Tie B", 200),  # created before Tie A
        ("Tie A", 200),
    ]  # Small (100) is cut off
    receivables = fetch(api, "summary")["receivables"]
    assert receivables["outstanding_paise"] == 40_501
    assert receivables["unapplied_credit_paise"] == 2_000
    # A member in credit is never listed, and what is listed never exceeds what is outstanding.
    assert all(m["balance_paise"] > 0 for m in top)
    assert "Credit" not in {m["member_name"] for m in top}
    assert sum(m["balance_paise"] for m in top) <= receivables["outstanding_paise"]


# --- no analytics request changes anything -----------------------------------------------------


@pytest.fixture
def busy_library(session_factory):
    """A library with a lapsed hold, an overdue loan, history, payments and a suspended member."""
    member = new_member(session_factory, name="Busy")
    reservation(
        session_factory, member, new_item(session_factory, name="Lapsed"), NOW - HOLD - HOUR
    )
    reservation(session_factory, member, new_item(session_factory, name="Fresh"), NOW - HOUR)
    checked_out_loan(session_factory, member, new_item(session_factory, name="Late"), NOW - 5 * DAY)
    returned_loan(
        session_factory,
        member,
        new_item(session_factory, name="Back"),
        due_at=NOW - 3 * DAY,
        returned_at=NOW - DAY,
        fee_paise=2_000,
    )
    payment(session_factory, member, NOW - HOUR, 500)
    suspended_member(session_factory, name="Suspended")


@pytest.mark.parametrize("name", ENDPOINTS)
def test_a_report_does_not_change_a_single_row_even_for_a_lapsed_hold(
    api, session_factory, busy_library, name
):
    before = snapshot(session_factory)

    for at in (NOW, NOW + 3 * DAY, NOW - 30 * DAY):
        fetch(api, name, at=at)
        fetch(api, name, at=at, days=366)

    assert snapshot(session_factory) == before
    reserved = [row for row in before["loans"] if "reserved" in row]
    assert len(reserved) == 2  # both holds are still stored as reserved


@pytest.mark.parametrize("name", ENDPOINTS)
def test_a_report_sends_only_read_statements_to_the_database(
    api, session_factory, busy_library, name
):
    with captured_sql(session_factory) as statements:
        fetch(api, name)

    verbs = {re.match(r"\s*(\w+)", statement).group(1).upper() for statement in statements}
    assert "SELECT" in verbs
    assert not verbs & {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "REPLACE"}


def test_reading_the_reports_does_not_expire_holds_for_the_item_endpoints_either(api, busy_library):
    items = api.get("/items?limit=200").json()["results"]
    lapsed = next(item for item in items if item["name"] == "Lapsed")
    for name in ENDPOINTS:
        fetch(api, name)

    assert api.get(f"/items/{lapsed['id']}").json()["status"] == "available"
    assert fetch(api, "summary")["loans"]["reserved"] == 1  # only the fresh hold


def _statement_count(session_factory, api, name) -> int:
    with captured_sql(session_factory) as statements:
        fetch(api, name)
    return len(statements)


@pytest.mark.parametrize("name", ENDPOINTS)
def test_the_number_of_queries_does_not_grow_with_the_amount_of_data(api, session_factory, name):
    new_member(session_factory, name="Only")
    small = _statement_count(session_factory, api, name)

    for number in range(25):
        member = new_member(session_factory, name=f"Member {number}")
        item = new_item(session_factory, name=f"Item {number}")
        checked_out_loan(session_factory, member, item, NOW - (number + 1) * DAY)
        returned_loan(
            session_factory,
            member,
            new_item(session_factory, name=f"Back {number}"),
            due_at=NOW - (number + 2) * HOUR,
            returned_at=NOW - number * HOUR - SECOND,
            fee_paise=1_000,
        )
        payment(session_factory, member, NOW - number * HOUR, 100)
    large = _statement_count(session_factory, api, name)

    assert large == small
    assert large <= 15


# --- the sample data ---------------------------------------------------------------------------


@pytest.fixture
def seeded(session_factory):
    run(session_factory, lambda session: seed_database(session, NOW))


def test_on_the_sample_data_every_report_agrees_with_the_existing_endpoints(api, seeded):
    summary = fetch(api, "summary")
    aging = fetch(api, "overdue-aging")
    payments = fetch(api, "payments")
    overdue = api.get("/loans/overdue?limit=200").json()
    items = api.get("/items?limit=200").json()
    members = api.get("/members?limit=200").json()

    assert overdue["total"] > 0  # the sample data deliberately contains late loans
    assert summary["fleet"]["total_items"] == items["total"]
    assert summary["members"]["total"] == members["total"]
    assert summary["loans"]["overdue"] == aging["open"]["count"] == overdue["total"]
    assert aging["open"]["accrued_fee_paise"] == sum(
        row["fee_if_returned_now_paise"] for row in overdue["results"]
    )
    assert aging["open"]["oldest_days_overdue"] == overdue["results"][0]["days_overdue"]
    statements = [api_statement(api, member["id"]) for member in members["results"]]
    balances = [s["balance_paise"] for s in statements]
    ledger = payments["ledger"]
    assert ledger["outstanding_paise"] == sum(b for b in balances if b > 0)
    assert ledger["unapplied_credit_paise"] == abs(sum(b for b in balances if b < 0))
    assert ledger["fees_charged_paise"] - ledger["collected_paise"] == sum(balances)
    assert summary["receivables"]["unapplied_credit_paise"] == ledger["unapplied_credit_paise"]
    assert summary["receivables"]["outstanding_paise"] == payments["ledger"]["outstanding_paise"]
    assert summary["members"]["blocked"] == sum(1 for s in statements if s["block_reasons"])
    assert summary["loans"]["active"] == sum(s["active_loan_count"] for s in statements)
    for status in ("available", "reserved", "checked_out", "overdue", "under_maintenance"):
        listed = api.get(f"/items?status={status}&limit=200").json()["total"]
        assert summary["fleet"][status] == listed, status


# --- partial buckets ----------------------------------------------------------------------------


def test_weekly_buckets_say_which_days_they_cover_and_which_are_partial(api):
    series = fetch(api, "payments", days=21, bucket="week", at=NOW + 8 * DAY)["series"]
    # 21 days ending Tue 20 Oct: Tue 30 Sep .. Tue 20 Oct.
    assert [
        (slot["start"], slot["covered_from"], slot["covered_to"], slot["partial"])
        for slot in series
    ] == [
        ("2026-09-28", "2026-09-30", "2026-10-04", True),  # the period starts on a Tuesday
        ("2026-10-05", "2026-10-05", "2026-10-11", False),
        ("2026-10-12", "2026-10-12", "2026-10-18", False),
        ("2026-10-19", "2026-10-19", "2026-10-20", True),  # this week is not over
    ]


def test_a_period_ending_on_a_sunday_still_has_a_partial_last_week(api):
    sunday = NOW + 6 * DAY  # Sun 18 Oct
    series = fetch(api, "payments", days=7, bucket="week", at=sunday)["series"]

    assert [(slot["start"], slot["partial"]) for slot in series] == [("2026-10-12", True)]


def test_only_the_bucket_holding_today_is_partial_when_bucketing_by_day(api):
    series = fetch(api, "payments", days=10)["series"]

    assert [slot["partial"] for slot in series] == [False] * 9 + [True]
    assert all(slot["covered_from"] == slot["covered_to"] == slot["start"] for slot in series)


def test_the_openapi_documents_partial_buckets_and_the_balance_definitions(api):
    schemas = api.get("/openapi.json").json()["components"]["schemas"]

    bucket = schemas["PaymentBucketRead"]["properties"]
    assert "weekly" in bucket["partial"]["description"]
    assert "today" in bucket["partial"]["description"]
    assert "inside the report period" in bucket["covered_from"]["description"]
    receivables = schemas["ReceivablesRead"]["properties"]
    assert "never negative" in receivables["outstanding_paise"]["description"]
    assert "negative balances" in receivables["unapplied_credit_paise"]["description"]
    assert "never listed" in schemas["PaymentsRead"]["properties"]["top_balances"]["description"]
    assert "like for like" in schemas["WindowRead"]["properties"]["previous_through"]["description"]


# --- rows dated after "now" are in no total ----------------------------------------------------


def owing_member(session_factory, name="Debtor"):
    """A member with a ₹50 fee from long ago, so the balance starts at 5,000 paise."""
    member = new_member(session_factory, name=name)
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - 100 * DAY,
        returned_at=NOW - 99 * DAY,
        fee_paise=5_000,
    )
    return member


def test_a_payment_dated_after_now_changes_nothing_until_the_clock_reaches_it(api, session_factory):
    member = owing_member(session_factory)
    payment(session_factory, member, NOW + SECOND, 2_000)

    before = fetch(api, "payments")
    after = fetch(api, "payments", at=NOW + SECOND)

    # At NOW the payment has not been made: it is not collected, not in the ledger, not in the
    # balance and not in the list of who owes most.
    assert before["collected"]["current"] == 0
    assert sum(slot["collected_paise"] for slot in before["series"]) == 0
    assert before["ledger"]["collected_paise"] == 0
    assert before["ledger"]["outstanding_paise"] == 5_000
    assert before["top_balances"] == [
        {"member_id": member, "member_name": "Debtor", "balance_paise": 5_000}
    ]
    assert fetch(api, "summary")["receivables"]["outstanding_paise"] == 5_000
    # One second later it is in every total, and they still agree with each other.
    assert after["collected"]["current"] == 2_000
    assert sum(slot["collected_paise"] for slot in after["series"]) == 2_000
    assert after["ledger"]["collected_paise"] == 2_000
    assert after["ledger"]["outstanding_paise"] == 3_000
    assert after["top_balances"][0]["balance_paise"] == 3_000
    assert fetch(api, "summary", at=NOW + SECOND)["receivables"]["outstanding_paise"] == 3_000


def test_a_future_payment_does_not_create_a_credit_before_it_is_made(api, session_factory):
    member = new_member(session_factory)
    payment(session_factory, member, NOW + SECOND, 2_000)

    assert fetch(api, "payments")["ledger"]["unapplied_credit_paise"] == 0
    assert fetch(api, "summary")["receivables"]["unapplied_credit_paise"] == 0
    assert fetch(api, "payments", at=NOW + SECOND)["ledger"]["unapplied_credit_paise"] == 2_000


def test_a_fee_charged_after_now_is_not_yet_owed(api, session_factory):
    member = new_member(session_factory, name="Later")
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - DAY,
        returned_at=NOW + SECOND,
        fee_paise=3_000,
    )

    before = fetch(api, "payments")
    after = fetch(api, "payments", at=NOW + SECOND)

    assert before["ledger"]["fees_charged_paise"] == 0
    assert before["ledger"]["outstanding_paise"] == 0
    assert before["top_balances"] == []
    assert before["fees_charged_paise"]["current"] == 0
    assert after["ledger"]["fees_charged_paise"] == after["fees_charged_paise"]["current"] == 3_000
    assert after["ledger"]["outstanding_paise"] == 3_000


def test_a_fee_charged_after_now_does_not_block_the_member_until_it_is_charged(
    api, session_factory
):
    member = new_member(session_factory, name="Later")
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - DAY,
        returned_at=NOW + SECOND,
        fee_paise=10_001,
    )

    assert fetch(api, "summary")["members"]["blocked_unpaid_fees"] == 0
    assert fetch(api, "summary")["receivables"]["members_over_limit"] == 0
    later = fetch(api, "summary", at=NOW + SECOND)
    assert later["members"]["blocked_unpaid_fees"] == 1
    assert later["receivables"]["members_over_limit"] == 1
    # The member endpoint agrees once the fee exists.
    assert api_member_view(api, member, at=NOW + SECOND)["block_reasons"] == ["unpaid_fees"]


@pytest.mark.parametrize("clock", [NOW - 3 * DAY, NOW, NOW + HOUR, NOW + 30 * DAY])
def test_the_ledger_balances_at_any_clock_even_with_rows_on_both_sides_of_it(
    api, session_factory, balances_library, clock
):
    payment(session_factory, balances_library["Small"], NOW + HOUR, 50)  # not made at NOW
    returned_loan(
        session_factory,
        balances_library["Settled"],
        new_item(session_factory),
        due_at=NOW,
        returned_at=NOW + 2 * HOUR,
        fee_paise=400,
    )

    ledger = fetch(api, "payments", at=clock)["ledger"]
    summary = fetch(api, "summary", at=clock)["receivables"]

    owed_minus_credit = ledger["outstanding_paise"] - ledger["unapplied_credit_paise"]
    assert ledger["fees_charged_paise"] - ledger["collected_paise"] == owed_minus_credit
    assert summary["outstanding_paise"] == ledger["outstanding_paise"]
    assert summary["unapplied_credit_paise"] == ledger["unapplied_credit_paise"]
    assert summary["members_with_balance"] == ledger["members_with_balance"]
    assert ledger["outstanding_paise"] >= 0
    assert ledger["unapplied_credit_paise"] >= 0


# --- the member endpoints keep counting every row; analytics stops at "now" ---------------------


def test_member_endpoints_still_count_future_dated_rows_while_analytics_does_not(
    api, session_factory
):
    """Existing behaviour, pinned on purpose: /members/{id} and its statement add up every fee and
    payment ever recorded, whatever the clock says. Analytics cuts both off at `as_of`."""
    member = owing_member(session_factory)  # a ₹50 fee from long ago
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - DAY,
        returned_at=NOW + 2 * SECOND,
        fee_paise=3_000,
    )  # a ₹30 fee that is charged after NOW
    payment(session_factory, member, NOW + SECOND, 2_000)  # a ₹20 payment made after NOW

    detail = api_member_view(api, member)
    statement = api_statement(api, member)
    ledger = fetch(api, "payments")["ledger"]

    assert detail["balance_paise"] == statement["balance_paise"] == 6_000  # 5,000 + 3,000 - 2,000
    assert statement["total_fees_paise"] == 8_000
    assert statement["total_payments_paise"] == 2_000
    assert len(statement["payments"]) == 1  # the payment dated after NOW is listed
    assert ledger["fees_charged_paise"] == 5_000
    assert ledger["collected_paise"] == 0
    assert ledger["outstanding_paise"] == 5_000
    assert fetch(api, "payments")["top_balances"][0]["balance_paise"] == 5_000


def test_once_the_clock_reaches_the_rows_analytics_and_the_member_endpoints_agree(
    api, session_factory
):
    member = owing_member(session_factory)
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - DAY,
        returned_at=NOW + 2 * SECOND,
        fee_paise=3_000,
    )
    payment(session_factory, member, NOW + SECOND, 2_000)
    later = NOW + 2 * SECOND

    statement = api_statement(api, member, at=later)
    data = fetch(api, "payments", at=later)

    assert data["ledger"]["fees_charged_paise"] == statement["total_fees_paise"] == 8_000
    assert data["ledger"]["collected_paise"] == statement["total_payments_paise"] == 2_000
    assert data["ledger"]["outstanding_paise"] == statement["balance_paise"] == 6_000
    assert data["top_balances"][0]["balance_paise"] == 6_000


def test_a_member_endpoint_blocks_on_a_future_fee_that_analytics_has_not_counted_yet(
    api, session_factory
):
    member = new_member(session_factory, name="Later")
    returned_loan(
        session_factory,
        member,
        new_item(session_factory),
        due_at=NOW - DAY,
        returned_at=NOW + SECOND,
        fee_paise=10_001,
    )

    assert api_member_view(api, member)["block_reasons"] == ["unpaid_fees"]  # existing behaviour
    assert fetch(api, "summary")["members"]["blocked_unpaid_fees"] == 0
    assert fetch(api, "summary", at=NOW + SECOND)["members"]["blocked_unpaid_fees"] == 1
