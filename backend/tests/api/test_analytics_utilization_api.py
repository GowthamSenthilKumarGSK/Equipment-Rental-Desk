"""GET /analytics/utilization: checked-out item-days against fleet item-days, by IST day or week."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.enums import ItemStatus, LoanStatus
from tests.api.analytics_helpers import (
    checked_out_loan,
    fetch,
    new_item,
    new_member,
    reservation,
    returned_loan,
)
from tests.builders import NOW

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
SECOND = timedelta(seconds=1)
# NOW is 15:30 IST on Mon 12 Oct 2026. A one-day report measures today so far: 15.5 hours.
TODAY_SO_FAR = timedelta(hours=15, minutes=30)


@pytest.fixture
def member(session_factory):
    return new_member(session_factory, name="Borrower")


def out_since(session_factory, member, item, start):
    """The item is checked out at `start` and still out."""
    checked_out_loan(session_factory, member, item, start + 7 * DAY)


def out_between(session_factory, member, item, start, end):
    returned_loan(
        session_factory, member, item, due_at=start + 7 * DAY, returned_at=end, checked_out_at=start
    )


def utilization(api, **params):
    return fetch(api, "utilization", **params)


# --- an empty library --------------------------------------------------------------------------


def test_with_no_items_everything_is_zero_and_the_percentages_are_null(api):
    data = utilization(api)

    zero = {"checked_out_item_days": 0.0, "fleet_item_days": 0.0, "utilization_pct": None}
    assert data["fleet"] == {"items": 0, "under_maintenance_now": 0}
    assert data["current"] == data["previous"] == zero
    assert data["change_points"] is None
    assert data["by_category"] == []
    assert data["bucket"] == "day"
    assert len(data["series"]) == 30
    assert all(slot["utilization_pct"] is None for slot in data["series"])


def test_items_that_were_never_lent_have_zero_utilization_not_null(api, session_factory):
    new_item(session_factory)
    new_item(session_factory, name="Second")

    data = utilization(api, days=1)

    assert data["current"] == {
        "checked_out_item_days": 0.0,
        "fleet_item_days": 1.29,  # 2 items x 15.5 hours
        "utilization_pct": 0.0,
    }
    assert data["change_points"] == 0.0


# --- the arithmetic ----------------------------------------------------------------------------


@pytest.fixture
def four_items(session_factory, member):
    """Four items on a one-day report (today so far = 15.5 h, so fleet time = 62 hours).

    A: out for 10 h so far. B: out 15 h ago, back 5 h ago = 10 h. C: out and back yesterday, before
    the measured time = 0 h (6 h of it inside the previous day's matching stretch). D: out 40 h
    ago, back 10 h ago = 5.5 h inside today (15.5 h inside the previous stretch).
    """
    items = [new_item(session_factory, name=name, category="Tools") for name in "ABCD"]
    a, b, c, d = items
    out_since(session_factory, member, a, NOW - 10 * HOUR)
    out_between(session_factory, member, b, NOW - 15 * HOUR, NOW - 5 * HOUR)
    out_between(session_factory, member, c, NOW - 30 * HOUR, NOW - 20 * HOUR)
    out_between(session_factory, member, d, NOW - 40 * HOUR, NOW - 10 * HOUR)
    return items


def test_utilization_is_checked_out_time_over_fleet_time(api, four_items):
    data = utilization(api, days=1)

    # 10 + 10 + 0 + 5.5 = 25.5 hours out of 4 x 15.5 = 62 hours
    assert data["current"] == {
        "checked_out_item_days": 1.06,  # 1.0625
        "fleet_item_days": 2.58,  # 2.5833
        "utilization_pct": 41.1,
    }


def test_the_previous_period_is_measured_over_the_same_length_of_time(api, four_items):
    data = utilization(api, days=1)

    # The 15.5 hours from yesterday's midnight: D is out all of it, C for 6 hours.
    assert data["previous"] == {
        "checked_out_item_days": 0.9,  # 21.5 hours
        "fleet_item_days": 2.58,  # the same 62 fleet hours
        "utilization_pct": 34.7,
    }
    assert data["change_points"] == 6.4
    window = data["window"]
    assert window["previous_through"] == "2026-10-11T10:00:00Z"
    assert window["start_date"] == window["end_date"] == "2026-10-12"


def test_the_daily_series_of_a_one_day_report_is_that_day_so_far(api, four_items):
    [slot] = utilization(api, days=1)["series"]

    assert slot == {
        "start": "2026-10-12",
        "covered_from": "2026-10-12",
        "covered_to": "2026-10-12",
        "partial": True,
        "checked_out_item_days": 1.06,
        "fleet_item_days": 2.58,
        "utilization_pct": 41.1,
    }


def test_a_loan_across_ist_midnight_is_split_between_the_two_days(api, session_factory, member):
    item = new_item(session_factory)
    # 23:30 IST on 11 Oct to 00:30 IST on 12 Oct.
    out_between(session_factory, member, item, NOW - 16 * HOUR, NOW - 15 * HOUR)

    data = utilization(api, days=3)

    assert [
        (
            s["start"],
            s["partial"],
            s["fleet_item_days"],
            s["checked_out_item_days"],
            s["utilization_pct"],
        )
        for s in data["series"]
    ] == [
        ("2026-10-10", False, 1.0, 0.0, 0.0),
        ("2026-10-11", False, 1.0, 0.02, 2.1),  # 30 minutes of 24 hours
        ("2026-10-12", True, 0.65, 0.02, 3.2),  # 30 minutes of 15.5 hours
    ]
    # 1 hour out of 63.5 hours measured
    assert data["current"] == {
        "checked_out_item_days": 0.04,
        "fleet_item_days": 2.65,
        "utilization_pct": 1.6,
    }


def test_weekly_buckets_start_on_monday_and_flag_the_cut_off_weeks(api, session_factory):
    new_item(session_factory)

    data = utilization(api, days=10, bucket="week")

    assert data["bucket"] == "week"
    # Sat 3 Oct .. Mon 12 Oct: two days of one week, a whole week, and today so far.
    assert [
        (s["start"], s["covered_from"], s["covered_to"], s["partial"], s["fleet_item_days"])
        for s in data["series"]
    ] == [
        ("2026-09-28", "2026-10-03", "2026-10-04", True, 2.0),
        ("2026-10-05", "2026-10-05", "2026-10-11", False, 7.0),
        ("2026-10-12", "2026-10-12", "2026-10-12", True, 0.65),
    ]
    assert data["current"]["fleet_item_days"] == 9.65


def test_the_series_adds_up_to_the_period_figures(api, session_factory, member):
    for number in range(5):
        item = new_item(session_factory, name=f"Item {number}")
        out_between(
            session_factory, member, item, NOW - (number + 1) * 31 * HOUR, NOW - number * 13 * HOUR
        )

    for bucket in ("day", "week"):
        data = utilization(api, days=14, bucket=bucket)
        assert sum(s["checked_out_item_days"] for s in data["series"]) == pytest.approx(
            data["current"]["checked_out_item_days"], abs=0.01 * len(data["series"])
        )
        assert sum(s["fleet_item_days"] for s in data["series"]) == pytest.approx(
            data["current"]["fleet_item_days"], abs=0.01 * len(data["series"])
        )


# --- what counts as checked out ----------------------------------------------------------------


def test_overdue_time_counts_as_checked_out(api, session_factory, member):
    item = new_item(session_factory)
    out_since(session_factory, member, item, NOW - 30 * DAY)  # due 23 days ago, never returned

    current = utilization(api, days=7)["current"]

    assert current["checked_out_item_days"] == current["fleet_item_days"] == 6.65
    assert current["utilization_pct"] == 100.0


def test_reserved_time_is_not_utilization(api, session_factory, member):
    reservation(session_factory, member, new_item(session_factory), NOW - 5 * HOUR)

    current = utilization(api, days=1)["current"]

    assert current["checked_out_item_days"] == 0.0 and current["utilization_pct"] == 0.0


def test_cancelled_and_expired_reservations_are_not_utilization(api, session_factory, member):
    reservation(
        session_factory, member, new_item(session_factory), NOW - 9 * HOUR, LoanStatus.CANCELLED
    )
    reservation(
        session_factory,
        member,
        new_item(session_factory, name="E"),
        NOW - 99 * HOUR,
        LoanStatus.EXPIRED,
    )

    assert utilization(api, days=7)["current"]["checked_out_item_days"] == 0.0


def test_time_after_now_is_not_counted(api, session_factory, member):
    returned_later = new_item(session_factory, name="Back later")
    out_between(session_factory, member, returned_later, NOW - 2 * HOUR, NOW + 5 * HOUR)
    not_yet = new_item(session_factory, name="Not yet")
    out_between(session_factory, member, not_yet, NOW + HOUR, NOW + 3 * HOUR)

    at_now = utilization(api, days=1)["current"]
    an_hour_on = utilization(api, days=1, at=NOW + HOUR)["current"]

    assert at_now["checked_out_item_days"] == 0.08  # only the 2 hours of "Back later"
    assert (
        an_hour_on["checked_out_item_days"] == 0.13
    )  # 3 hours (0.125 days, half up); "Not yet" has just begun


def test_the_edges_of_the_measured_time_are_exact(api, session_factory, member):
    start = NOW - TODAY_SO_FAR  # today's IST midnight
    for number, (out, back) in enumerate(
        [
            (start - 5 * HOUR, start),  # returned exactly at the start: nothing inside
            (start - 5 * HOUR, start + HOUR),  # 1 hour inside
            (NOW, NOW + HOUR),  # begins exactly now: nothing yet
            (NOW - HOUR, NOW),  # 1 hour, ending exactly now
        ]
    ):
        out_between(session_factory, member, new_item(session_factory, name=str(number)), out, back)

    current = utilization(api, days=1)["current"]

    assert current["checked_out_item_days"] == 0.08  # 2 hours


def test_the_test_clock_moves_the_measured_time(api, session_factory, member):
    out_since(session_factory, member, new_item(session_factory), NOW - 10 * HOUR)

    assert utilization(api, days=1)["current"]["checked_out_item_days"] == 0.42  # 10 hours
    assert utilization(api, days=1, at=NOW + HOUR)["current"]["checked_out_item_days"] == 0.46


def test_at_ist_midnight_no_time_has_passed_so_nothing_can_be_a_percentage(api, session_factory):
    new_item(session_factory)
    midnight = datetime(2026, 10, 12, 18, 30, tzinfo=UTC)  # 00:00 IST on 13 Oct

    data = utilization(api, days=2, at=midnight)

    assert data["window"]["end_date"] == "2026-10-13"
    assert data["series"][-1]["fleet_item_days"] == 0.0
    assert data["series"][-1]["utilization_pct"] is None
    assert data["series"][-1]["partial"] is True
    assert data["current"]["fleet_item_days"] == 1.0  # only yesterday has passed


# --- maintenance has no history ----------------------------------------------------------------


def test_items_under_maintenance_stay_in_the_fleet_because_the_past_is_unknown(
    api, session_factory, member
):
    new_item(session_factory, name="Idle")
    new_item(session_factory, name="Broken", status=ItemStatus.UNDER_MAINTENANCE)
    pulled = new_item(session_factory, name="Pulled")
    checked_out_loan(session_factory, member, pulled, NOW + 2 * DAY, ItemStatus.UNDER_MAINTENANCE)

    data = utilization(api, days=1)

    assert data["fleet"] == {"items": 3, "under_maintenance_now": 2}
    assert (
        data["fleet"]["under_maintenance_now"]
        == api.get("/items?status=under_maintenance", at=NOW).json()["total"]
    )
    # All three items are fleet time (3 x 15.5 h); nothing is subtracted for maintenance. The
    # loan of the item pulled into maintenance was out for 5 days: 15.5 h inside today.
    assert data["current"]["fleet_item_days"] == 1.94
    assert data["current"]["checked_out_item_days"] == 0.65
    assert data["current"]["utilization_pct"] == 33.3


def test_the_openapi_states_the_maintenance_limitation(api):
    schemas = api.get("/openapi.json").json()["components"]["schemas"]

    text = schemas["UtilizationRead"]["description"]
    assert "no maintenance history" in text and "Nothing is estimated" in text
    assert (
        "maintenance"
        in schemas["UtilizationFleetRead"]["properties"]["under_maintenance_now"]["description"]
    )
    assert (
        "Reserved time is not counted"
        in schemas["UtilizationFigureRead"]["properties"]["checked_out_item_days"]["description"]
    )


# --- categories --------------------------------------------------------------------------------


def test_categories_are_grouped_without_regard_to_case_and_ranked_by_time_out(
    api, session_factory, member
):
    first = new_item(session_factory, name="Drill", category="Power Tools")
    second = new_item(session_factory, name="Saw", category="Power Tools")
    third = new_item(session_factory, name="Sander", category="power tools")
    rake = new_item(session_factory, name="Rake", category="Garden")
    out_since(session_factory, member, first, NOW - 3 * HOUR)
    out_since(session_factory, member, third, NOW - 6 * HOUR)
    out_between(session_factory, member, rake, NOW - 2 * HOUR, NOW - HOUR)
    assert second  # never lent

    data = utilization(api, days=1)

    assert data["by_category"] == [
        {
            "category": "Power Tools",
            "items": 3,
            "checked_out_item_days": 0.38,  # 9 hours
            "fleet_item_days": 1.94,  # 3 x 15.5 hours
            "utilization_pct": 19.4,
        },
        {
            "category": "Garden",
            "items": 1,
            "checked_out_item_days": 0.04,
            "fleet_item_days": 0.65,
            "utilization_pct": 6.5,
        },
    ]
    assert sum(c["items"] for c in data["by_category"]) == data["fleet"]["items"]


def test_a_category_nobody_borrowed_from_is_listed_with_zero(api, session_factory, member):
    out_since(session_factory, member, new_item(session_factory, category="Tools"), NOW - HOUR)
    new_item(session_factory, name="Tent", category="Camping")

    categories = utilization(api, days=1)["by_category"]

    assert [c["category"] for c in categories] == ["Tools", "Camping"]
    assert categories[1]["utilization_pct"] == 0.0


# --- agreement with the existing endpoints -----------------------------------------------------


def test_loans_made_through_the_api_give_exact_item_days(api):
    member = api.make_member()
    returned = api.make_item(name="Returned")
    still_out = api.make_item(name="Still out")
    api.rent(returned["id"], member["id"], at=NOW - 2 * DAY)
    assert api.post(f"/items/{returned['id']}/return", at=NOW - DAY).status_code == 200
    api.rent(still_out["id"], member["id"], at=NOW - 3 * HOUR)

    data = utilization(api, days=7)

    # 24 hours + 3 hours = 27 hours = 1.125 days; fleet = 2 x 6d 15.5h = 13.29 days
    assert data["current"]["checked_out_item_days"] == 1.13
    assert data["current"]["fleet_item_days"] == 13.29
    assert data["current"]["utilization_pct"] == 8.5
    assert data["fleet"]["items"] == api.get("/items", at=NOW).json()["total"] == 2


def test_the_items_checked_out_now_are_the_ones_counted_as_still_running(
    api, session_factory, member
):
    for number in range(3):
        out_since(session_factory, member, new_item(session_factory, name=str(number)), NOW - HOUR)

    open_now = api.get("/items?status=checked_out", at=NOW).json()["total"]
    data = utilization(api, days=1)

    # Every item currently out has been out for the last hour.
    assert open_now == 3
    assert data["current"]["checked_out_item_days"] == 0.13  # 3 hours = 0.125 days, half up


# --- parameters --------------------------------------------------------------------------------


@pytest.mark.parametrize("bucket", ["month", "DAY", "weekly", ""])
def test_an_unknown_bucket_is_422(api, bucket):
    assert api.get(f"/analytics/utilization?bucket={bucket}").status_code == 422


def test_utilization_and_demand_only_answer_get(api):
    for path in ("/analytics/utilization", "/analytics/demand"):
        for method in ("post", "patch", "delete"):
            assert getattr(api, method)(path).status_code == 405


# --- the end of the previous measured time ------------------------------------------------------


def test_a_loan_starting_exactly_at_previous_through_adds_nothing_to_the_previous_period(
    api, session_factory, member
):
    through = NOW - 7 * DAY
    at_edge = new_item(session_factory, name="At the edge")
    out_between(session_factory, member, at_edge, through, through + 8 * HOUR)
    early = new_item(session_factory, name="A little earlier")
    out_between(session_factory, member, early, through - 8 * 60 * SECOND, through + 8 * HOUR)

    data = utilization(api, days=7)

    assert data["window"]["previous_through"] == "2026-10-05T10:00:00Z"
    # Only the 8 minutes before the edge are measured (0.0056 days, shown as 0.01); the eight hours
    # that follow it belong to a stretch the previous period is not measured over.
    assert data["previous"]["checked_out_item_days"] == 0.01
    assert data["current"]["checked_out_item_days"] == 0.0


def test_the_openapi_describes_previous_through_for_counts_and_for_utilization(api):
    schemas = api.get("/openapi.json").json()["components"]["schemas"]

    text = schemas["WindowRead"]["properties"]["previous_through"]["description"]
    assert "like for like" in text
    assert "exactly at this instant" in text
    assert "half-open" in text and "not including" in text


# --- category order and the database's own case folding ------------------------------------------


def test_equal_categories_are_ordered_by_name_ignoring_case(api, session_factory):
    for number, category in enumerate(["Zebra", "apple", "Mango", "banana"]):
        new_item(session_factory, name=f"Item {number}", category=category)

    categories = [c["category"] for c in utilization(api, days=1)["by_category"]]

    assert categories == ["apple", "banana", "Mango", "Zebra"]  # not Mango, Zebra, apple, banana


def test_time_out_still_ranks_before_the_name(api, session_factory, member):
    for number, (category, hours) in enumerate([("apple", 0), ("Zebra", 5), ("banana", 5)]):
        item = new_item(session_factory, name=f"Item {number}", category=category)
        if hours:
            out_since(session_factory, member, item, NOW - hours * HOUR)

    categories = [c["category"] for c in utilization(api, days=1)["by_category"]]

    assert categories == ["banana", "Zebra", "apple"]  # equal time out: by name; none: last


def test_categories_that_differ_only_in_the_case_of_ascii_letters_are_one_group(
    api, session_factory
):
    for number, category in enumerate(["Café", "CAFé", "café"]):
        new_item(session_factory, name=f"Item {number}", category=category)

    [group] = utilization(api, days=1)["by_category"]

    assert group["items"] == 3
    # The same three items the category filter of /items finds, on every database.
    assert api.get("/items?category=café&limit=50", at=NOW).json()["total"] == 3


def test_uppercase_non_ascii_letters_group_the_way_the_database_folds_them_like_the_items_filter(
    api, session_factory
):
    for number, category in enumerate(["École", "ÉCOLE", "école"]):
        new_item(session_factory, name=f"Item {number}", category=category)

    groups = utilization(api, days=1)["by_category"]
    sizes = sorted(g["items"] for g in groups)

    # How many items share a group depends on the database's lower(): SQLite folds ASCII letters
    # only, so "école" is alone (groups of 1 and 2); PostgreSQL's UTF-8 locale folds the accented
    # capital too, so all three are one group (3). Nothing else is acceptable. The name of a group
    # is its first spelling in string order, so it is "ÉCOLE" when the three are merged.
    assert sizes in ([3], [1, 2])
    # Whichever it is, the items `GET /items?category=école` returns (those whose lower-cased
    # category is "école") are exactly one group: the dashboard never groups differently from the
    # filter.
    found = api.get("/items?category=école&limit=50", at=NOW).json()
    assert found["total"] in sizes


def test_on_sqlite_the_ascii_only_fold_makes_two_groups_just_like_the_items_filter(
    api, session_factory
):
    if session_factory.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite's lower() folds only ASCII letters; other databases fold more")
    for number, category in enumerate(["École", "ÉCOLE", "école"]):
        new_item(session_factory, name=f"Item {number}", category=category)

    groups = utilization(api, days=1)["by_category"]

    assert sorted(g["items"] for g in groups) == [1, 2]
    # Order of the two equal groups: ignoring case they tie, then exact spelling decides.
    assert [g["category"] for g in groups] == sorted(
        (g["category"] for g in groups), key=lambda c: (c.casefold(), c)
    )
    assert api.get("/items?category=école&limit=50", at=NOW).json()["total"] == 1
