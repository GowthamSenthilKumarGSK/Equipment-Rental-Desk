"""The analytics endpoints on an empty library, with bad input and under the reviewer test clock."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.api.analytics_helpers import fetch, new_member, payment
from tests.api.conftest import error_code
from tests.builders import NOW

ENDPOINTS = ["summary", "overdue-aging", "payments", "utilization", "demand"]
ZERO_CHANGE = {"current": 0, "previous": 0, "change_pct": None}
# NOW is 12 Oct 2026 15:30 IST. A 30-day report is 13 Sep .. 12 Oct; the 30 days before end 12 Sep.
WINDOW_30 = {
    "days": 30,
    "start_date": "2026-09-13",
    "end_date": "2026-10-12",
    "previous_start_date": "2026-08-14",
    "previous_end_date": "2026-09-12",
    # Today is only half over, so the previous period is counted only up to the same point in time.
    "previous_through": "2026-09-12T10:00:00Z",
    "timezone": "Asia/Kolkata (IST, UTC+05:30)",
}


def test_an_empty_library_gives_zeros_and_nulls_never_errors_or_nan(api):
    summary = fetch(api, "summary")

    assert summary["as_of"] == "2026-10-12T10:00:00Z"
    assert summary["window"] == WINDOW_30
    assert summary["fleet"] == {
        "total_items": 0,
        "available": 0,
        "reserved": 0,
        "checked_out": 0,
        "overdue": 0,
        "under_maintenance": 0,
    }
    assert summary["loans"] == {
        "active": 0,
        "reserved": 0,
        "checked_out": 0,
        "overdue": 0,
        "overdue_share_pct": None,
    }
    assert summary["members"] == {
        "total": 0,
        "active": 0,
        "suspended": 0,
        "blocked": 0,
        "blocked_suspended": 0,
        "blocked_unpaid_fees": 0,
        "blocked_long_overdue": 0,
    }
    assert summary["receivables"] == {
        "outstanding_paise": 0,
        "unapplied_credit_paise": 0,
        "members_with_balance": 0,
        "members_over_limit": 0,
    }
    for name in (
        "reservations_created",
        "checkouts",
        "returns",
        "payments_collected_paise",
        "fees_charged_paise",
    ):
        assert summary[name] == ZERO_CHANGE, name
    assert summary["late_return_rate"] == {"current_pct": None, "previous_pct": None}


def test_overdue_aging_on_an_empty_library(api):
    aging = fetch(api, "overdue-aging")

    assert aging["window"] == WINDOW_30
    assert aging["open"]["count"] == 0
    assert aging["open"]["accrued_fee_paise"] == 0
    assert aging["open"]["blocking_count"] == 0
    assert aging["open"]["oldest_days_overdue"] is None
    assert [
        (b["label"], b["min_days"], b["max_days"], b["count"], b["accrued_fee_paise"])
        for b in aging["open"]["bands"]
    ] == [
        ("1–3 days", 1, 3, 0, 0),
        ("4–7 days", 4, 7, 0, 0),
        ("8–14 days", 8, 14, 0, 0),
        ("15+ days", 15, None, 0, 0),
    ]
    assert aging["top_members"] == []
    assert aging["returns"] == {
        "returned": 0,
        "late": 0,
        "late_rate_pct": None,
        "average_days_late": None,
        "fees_charged_paise": 0,
    }


def test_payments_on_an_empty_library_have_a_zero_filled_series(api):
    payments = fetch(api, "payments")

    assert payments["bucket"] == "day"
    assert payments["collected"] == ZERO_CHANGE
    assert payments["payments"] == ZERO_CHANGE
    assert payments["average_payment_paise"] is None
    assert payments["collected_to_charged_pct"] is None
    assert len(payments["series"]) == 30
    assert payments["series"][0] == {
        "start": "2026-09-13",
        "collected_paise": 0,
        "count": 0,
        "covered_from": "2026-09-13",
        "covered_to": "2026-09-13",
        "partial": False,
    }
    assert payments["series"][-1] == {  # today is not over yet
        "start": "2026-10-12",
        "collected_paise": 0,
        "count": 0,
        "covered_from": "2026-10-12",
        "covered_to": "2026-10-12",
        "partial": True,
    }
    assert [slot["partial"] for slot in payments["series"]].count(True) == 1
    assert payments["ledger"] == {
        "fees_charged_paise": 0,
        "collected_paise": 0,
        "outstanding_paise": 0,
        "unapplied_credit_paise": 0,
        "members_with_balance": 0,
        "members_over_limit": 0,
    }
    assert payments["top_balances"] == []


# --- the days and bucket parameters -------------------------------------------------------------


@pytest.mark.parametrize("name", ENDPOINTS)
@pytest.mark.parametrize("days", ["0", "-1", "367", "1000", "abc", "7.5", ""])
def test_days_outside_1_to_366_or_not_a_whole_number_is_422(api, name, days):
    response = api.get(f"/analytics/{name}?days={days}")

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert "days" in str(response.json()["error"]["details"])


@pytest.mark.parametrize("bucket", ["month", "DAY", "weekly", ""])
def test_an_unknown_bucket_is_422(api, bucket):
    response = api.get(f"/analytics/payments?bucket={bucket}")

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


@pytest.mark.parametrize("name", ENDPOINTS)
def test_the_default_period_is_30_days(api, name):
    assert fetch(api, name)["window"]["days"] == 30


@pytest.mark.parametrize("name", ENDPOINTS)
@pytest.mark.parametrize("days", [1, 366])
def test_the_smallest_and_largest_periods_work(api, name, days):
    data = fetch(api, name, days=days)

    assert data["window"]["days"] == days
    start = datetime.fromisoformat(data["window"]["start_date"])
    end = datetime.fromisoformat(data["window"]["end_date"])
    assert (end - start).days == days - 1


def test_payments_series_has_one_entry_per_day_or_per_week(api):
    assert len(fetch(api, "payments", days=366)["series"]) == 366
    weekly = fetch(api, "payments", days=14, bucket="week")["series"]
    # 29 Sep .. 12 Oct touches the weeks beginning Mon 28 Sep, 5 Oct and 12 Oct.
    assert [slot["start"] for slot in weekly] == ["2026-09-28", "2026-10-05", "2026-10-12"]
    assert all(datetime.fromisoformat(slot["start"]).weekday() == 0 for slot in weekly)


def test_unknown_query_parameters_are_ignored_like_everywhere_else_in_the_api(api):
    assert fetch(api, "summary", days=7, colour="red")["window"]["days"] == 7


def test_analytics_only_answers_get(api):
    for method in ("post", "patch", "delete"):
        assert getattr(api, method)("/analytics/summary").status_code == 405


# --- the reviewer test clock --------------------------------------------------------------------


@pytest.mark.parametrize("name", ENDPOINTS)
def test_an_invalid_test_clock_is_a_400_for_every_report(api, name):
    for value in ("yesterday", "2026-10-12T10:00:00", "9999-12-31T23:59:59Z"):
        response = api.get(f"/analytics/{name}", at=None, headers={"X-Test-Clock": value})
        assert response.status_code == 400
        assert error_code(response) == "invalid_test_clock"


@pytest.mark.parametrize("name", ENDPOINTS)
def test_the_report_is_calculated_as_of_the_test_clock(api, name):
    later = datetime(2026, 11, 20, 4, 30, tzinfo=UTC)  # 10:00 IST on 20 Nov

    data = fetch(api, name, at=later, days=7)

    assert data["as_of"] == "2026-11-20T04:30:00Z"
    assert data["window"]["end_date"] == "2026-11-20"
    assert data["window"]["start_date"] == "2026-11-14"


def test_the_reporting_day_turns_over_at_ist_midnight_not_utc_midnight(api):
    before = datetime(2026, 10, 12, 18, 29, 59, tzinfo=UTC)  # 23:59:59 IST on 12 Oct
    after = before + timedelta(seconds=1)  # 00:00:00 IST on 13 Oct

    assert fetch(api, "summary", at=before, days=1)["window"]["end_date"] == "2026-10-12"
    assert fetch(api, "summary", at=after, days=1)["window"]["end_date"] == "2026-10-13"
    # UTC midnight is mid-morning in India: the Indian date is still the 12th.
    midnight_utc = datetime(2026, 10, 12, 0, 0, tzinfo=UTC)
    assert fetch(api, "summary", at=midnight_utc, days=1)["window"]["end_date"] == "2026-10-12"


def test_without_a_test_clock_the_real_time_is_used(api):
    response = api.get("/analytics/summary", at=None)

    assert response.status_code == 200
    as_of = datetime.fromisoformat(response.json()["as_of"].replace("Z", "+00:00"))
    assert abs(datetime.now(UTC) - as_of) < timedelta(minutes=5)


@pytest.mark.parametrize("name", ENDPOINTS)
def test_the_same_request_gives_the_same_answer_twice(api, name):
    assert fetch(api, name) == fetch(api, name)


# --- today is not over: the previous period is compared up to the same point -------------------


@pytest.mark.parametrize("name", ENDPOINTS)
@pytest.mark.parametrize("days", [1, 7, 30, 366])
@pytest.mark.parametrize(
    "moment",
    [
        datetime(2026, 10, 12, 10, 0, tzinfo=UTC),  # 15:30 IST
        datetime(2026, 10, 12, 18, 30, tzinfo=UTC),  # 00:00 IST: nothing of today has happened
        datetime(2026, 10, 12, 18, 29, 59, 999999, tzinfo=UTC),  # a microsecond before midnight
    ],
)
def test_the_previous_period_is_compared_up_to_the_same_point_as_the_current_one(
    api, name, days, moment
):
    window = fetch(api, name, at=moment, days=days)["window"]

    assert window["previous_through"] == (moment - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ" if moment.microsecond else "%Y-%m-%dT%H:%M:%SZ"
    )
    previous_start = datetime.fromisoformat(window["previous_start_date"])
    previous_end = datetime.fromisoformat(window["previous_end_date"])
    # the last compared day is the same number of days into the previous period as today is
    assert (previous_end - previous_start).days == days - 1


def test_the_previous_period_is_not_compared_beyond_the_same_hour_of_its_last_day(
    api, session_factory
):
    """A payment late on the last evening of the previous period is not set against today's
    half-finished day, so a quiet morning does not look like a collapse."""
    member = new_member(session_factory)
    previous_evening = NOW - timedelta(days=1) + timedelta(hours=6)  # 21:30 IST yesterday
    previous_morning = NOW - timedelta(days=1) - timedelta(hours=3)  # 12:30 IST yesterday
    payment(session_factory, member, previous_morning, 100)
    payment(session_factory, member, previous_evening, 900)  # after the matching point
    payment(session_factory, member, NOW - timedelta(hours=1), 100)

    collected = fetch(api, "payments", days=1)["collected"]

    assert collected == {"current": 100, "previous": 100, "change_pct": 0.0}
    # Later in the day the same evening payment joins the comparison.
    evening = fetch(api, "payments", at=previous_evening + timedelta(days=1), days=1)["collected"]
    assert evening["previous"] == 1_000


def test_the_comparison_includes_the_matching_instant_but_not_a_microsecond_more(
    api, session_factory
):
    member = new_member(session_factory)
    through = NOW - timedelta(days=7)
    payment(session_factory, member, through, 300)
    payment(session_factory, member, through + timedelta(microseconds=1), 7_000)

    collected = fetch(api, "payments", days=7)["collected"]

    assert collected["previous"] == 300
