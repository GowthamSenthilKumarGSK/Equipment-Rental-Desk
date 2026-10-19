"""GET /analytics/maintenance: a snapshot of the items under maintenance, never a history."""

import re
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.enums import ItemStatus, LoanStatus
from app.models import Item, Member
from tests.api.analytics_helpers import (
    captured_sql,
    checked_out_loan,
    fetch,
    new_item,
    new_member,
    reservation,
    run,
    snapshot,
)
from tests.api.conftest import error_code
from tests.builders import NOW, add_loan

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
BROKEN = ItemStatus.UNDER_MAINTENANCE


def maintenance(api, **kwargs):
    return fetch(api, "maintenance", **kwargs)


@pytest.fixture
def member(session_factory):
    return new_member(session_factory, name="Borrower")


@pytest.fixture
def workshop(session_factory, member):
    """Eight items: four under maintenance (two idle, one on loan on time, one on a late loan) and
    four that are not."""
    new_item(session_factory, name="Idle", category="Tools")
    new_item(
        session_factory,
        name="Drill",
        category="Power Tools",
        status=BROKEN,
        condition_note="Chuck jammed",
    )
    new_item(session_factory, name="Saw", category="power tools", status=BROKEN)
    pulled = new_item(session_factory, name="Pulled", category="Garden")
    checked_out_loan(session_factory, member, pulled, NOW + 2 * DAY, BROKEN)
    mower = new_item(session_factory, name="Mower", category="Garden")
    checked_out_loan(session_factory, member, mower, NOW - 3 * DAY, BROKEN)
    held = new_item(session_factory, name="Held", category="Tools")
    reservation(session_factory, member, held, NOW - HOUR)
    out = new_item(session_factory, name="Out", category="Tools")
    checked_out_loan(session_factory, member, out, NOW + 3 * DAY)
    late = new_item(session_factory, name="Late", category="Tools")
    checked_out_loan(session_factory, member, late, NOW - DAY)


# --- an empty library --------------------------------------------------------------------------


def test_with_no_items_everything_is_zero_and_there_is_no_percentage(api):
    data = maintenance(api)

    assert data["as_of"] == "2026-10-12T10:00:00Z"
    assert data["history_available"] is False
    assert data["fleet"] == {
        "total_items": 0,
        "available": 0,
        "reserved": 0,
        "checked_out": 0,
        "overdue": 0,
        "under_maintenance": 0,
    }
    assert data["share_of_fleet_pct"] is None
    assert (data["on_loan"], data["on_loan_overdue"], data["without_open_loan"]) == (0, 0, 0)
    assert data["by_category"] == []
    assert data["items"] == [] and data["items_truncated"] is False


def test_with_items_but_none_in_maintenance_the_share_is_zero_not_null(api, session_factory):
    new_item(session_factory, name="Drill", category="Tools")
    new_item(session_factory, name="Tent", category="Camping")

    data = maintenance(api)

    assert data["share_of_fleet_pct"] == 0.0
    assert data["fleet"]["under_maintenance"] == 0
    assert data["items"] == []
    assert [
        (c["category"], c["items"], c["under_maintenance"], c["share_pct"])
        for c in data["by_category"]
    ] == [("Camping", 1, 0, 0.0), ("Tools", 1, 0, 0.0)]


# --- the snapshot ------------------------------------------------------------------------------


def test_the_fleet_and_the_maintenance_figures(api, workshop):
    data = maintenance(api)

    assert data["fleet"] == {
        "total_items": 8,
        "available": 1,
        "reserved": 1,
        "checked_out": 1,
        "overdue": 1,  # "Late"; the late loan on "Mower" is counted under maintenance instead
        "under_maintenance": 4,
    }
    assert data["share_of_fleet_pct"] == 50.0
    assert data["on_loan"] == 2  # Pulled and Mower: a member still has them
    assert data["on_loan_overdue"] == 1  # Mower
    assert data["without_open_loan"] == 2  # Drill and Saw can be brought back now
    assert data["on_loan"] + data["without_open_loan"] == data["fleet"]["under_maintenance"]


def test_the_items_are_listed_by_name_with_their_open_loan(api, workshop):
    items = maintenance(api)["items"]

    assert [i["item_name"] for i in items] == ["Drill", "Mower", "Pulled", "Saw"]
    by_name = {i["item_name"]: i for i in items}
    assert by_name["Drill"]["condition_note"] == "Chuck jammed"
    assert by_name["Drill"]["category"] == "Power Tools"
    assert by_name["Drill"]["open_loan"] is None and by_name["Saw"]["open_loan"] is None
    mower = by_name["Mower"]["open_loan"]
    assert (mower["overdue"], mower["days_overdue"]) == (True, 3)
    assert mower["due_at"] == "2026-10-09T10:00:00Z"
    pulled = by_name["Pulled"]["open_loan"]
    assert (pulled["overdue"], pulled["days_overdue"]) == (False, 0)
    assert pulled["due_at"] == "2026-10-14T10:00:00Z"


def test_categories_are_grouped_like_elsewhere_and_ranked_by_items_under_maintenance(api, workshop):
    categories = maintenance(api)["by_category"]

    assert categories == [
        {"category": "Garden", "items": 2, "under_maintenance": 2, "share_pct": 100.0},
        {"category": "Power Tools", "items": 2, "under_maintenance": 2, "share_pct": 100.0},
        {"category": "Tools", "items": 4, "under_maintenance": 0, "share_pct": 0.0},
    ]  # "Power Tools" and "power tools" are one category; equal counts are ordered by name


def test_a_late_loan_on_a_maintenance_item_follows_the_clock(api, workshop):
    later = NOW + 3 * DAY  # "Pulled" was due at NOW + 2 days

    data = maintenance(api, at=later)
    pulled = next(i for i in data["items"] if i["item_name"] == "Pulled")["open_loan"]

    assert (pulled["overdue"], pulled["days_overdue"]) == (True, 1)
    assert data["on_loan_overdue"] == 2
    assert data["fleet"]["under_maintenance"] == 4  # maintenance itself does not move


def test_the_maintenance_status_does_not_depend_on_the_clock(api, workshop):
    for moment in (NOW - 90 * DAY, NOW, NOW + 90 * DAY):
        data = maintenance(api, at=moment)
        assert data["fleet"]["under_maintenance"] == 4
        assert [i["item_name"] for i in data["items"]] == ["Drill", "Mower", "Pulled", "Saw"]
        assert data["as_of"] == moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.parametrize(
    ("late_by", "overdue", "days"),
    [
        (-HOUR, False, 0),
        (timedelta(0), False, 0),  # exactly at the due time is still on time
        (timedelta(seconds=1), True, 1),
        (DAY, True, 1),
        (DAY + timedelta(seconds=1), True, 2),
    ],
)
def test_a_loan_on_a_maintenance_item_turns_overdue_just_after_its_due_time(
    api, session_factory, member, late_by, overdue, days
):
    item = new_item(session_factory, name="Drill", status=BROKEN)
    checked_out_loan(session_factory, member, item, NOW - late_by, BROKEN)

    data = maintenance(api)

    loan = data["items"][0]["open_loan"]
    assert (loan["overdue"], loan["days_overdue"]) == (overdue, days)
    assert data["on_loan_overdue"] == (1 if overdue else 0)
    assert data["fleet"]["overdue"] == 0  # the item is under maintenance, not "overdue"


def test_categories_with_equal_counts_are_ordered_by_name_ignoring_case(api, session_factory):
    for number, category in enumerate(["Zebra", "apple", "Mango"]):
        new_item(session_factory, name=f"Broken {number}", category=category, status=BROKEN)
    new_item(session_factory, name="Fine zoo", category="Zoo")
    new_item(session_factory, name="Fine bird", category="bird")

    categories = [c["category"] for c in maintenance(api)["by_category"]]

    assert categories == ["apple", "Mango", "Zebra", "bird", "Zoo"]


def test_an_unexpected_reservation_on_a_maintenance_item_is_not_shown_as_a_loan(
    api, session_factory, member
):
    """Maintenance cancels reservations, so this cannot arise through the API; if the data ever
    holds one, it must not be reported as a loan the member has (it has no due time)."""
    item = new_item(session_factory, name="Odd", status=BROKEN)
    run(
        session_factory,
        lambda s: add_loan(
            s, s.get(Member, member), s.get(Item, item), LoanStatus.RESERVED, reserved_at=NOW - HOUR
        ),
    )

    data = maintenance(api)

    assert data["items"][0]["open_loan"] is None
    assert (data["on_loan"], data["without_open_loan"]) == (0, 1)


# --- agreement with the existing endpoints -----------------------------------------------------


def test_the_fleet_is_the_fleet_of_the_summary_and_of_the_item_list(api, workshop):
    data = maintenance(api)

    assert data["fleet"] == fetch(api, "summary")["fleet"]
    for key, status in [
        ("available", "available"),
        ("reserved", "reserved"),
        ("checked_out", "checked_out"),
        ("overdue", "overdue"),
        ("under_maintenance", "under_maintenance"),
    ]:
        listed = api.get(f"/items?status={status}&limit=200", at=NOW).json()["total"]
        assert data["fleet"][key] == listed, key
    assert data["fleet"]["total_items"] == api.get("/items?limit=200", at=NOW).json()["total"]


def test_the_listed_items_are_the_ones_the_item_endpoint_puts_under_maintenance(api, workshop):
    data = maintenance(api)

    listed = api.get("/items?status=under_maintenance&limit=200", at=NOW).json()["results"]
    assert sorted(i["item_id"] for i in data["items"]) == sorted(i["id"] for i in listed)
    assert sorted(c["under_maintenance"] for c in data["by_category"]) == [0, 2, 2]
    assert sum(c["under_maintenance"] for c in data["by_category"]) == len(listed)
    assert sum(c["items"] for c in data["by_category"]) == data["fleet"]["total_items"]


def test_staff_can_bring_back_exactly_the_items_without_an_open_loan(api, workshop):
    data = maintenance(api)

    for entry in data["items"]:
        allowed = api.get(f"/items/{entry['item_id']}", at=NOW).json()["allowed_actions"]
        assert ("finish_maintenance" in allowed) == (entry["open_loan"] is None), entry
    freeable = [i for i in data["items"] if i["open_loan"] is None]
    assert len(freeable) == data["without_open_loan"]


def test_the_late_loans_are_those_of_the_overdue_loans_endpoint(api, workshop):
    data = maintenance(api)

    overdue = api.get("/loans/overdue?limit=200", at=NOW).json()
    on_maintenance_items = {i["item_id"] for i in data["items"]}
    late_on_maintenance = [r for r in overdue["results"] if r["item_id"] in on_maintenance_items]
    assert len(late_on_maintenance) == data["on_loan_overdue"]
    # Every late loan is either an overdue item or a late loan on a maintenance item.
    assert overdue["total"] == data["fleet"]["overdue"] + data["on_loan_overdue"]
    mower = next(i for i in data["items"] if i["item_name"] == "Mower")
    row = next(r for r in overdue["results"] if r["item_id"] == mower["item_id"])
    assert row["days_overdue"] == mower["open_loan"]["days_overdue"]
    assert row["due_at"] == mower["open_loan"]["due_at"]


def test_putting_an_item_on_loan_into_maintenance_through_the_api_is_reflected_step_by_step(api):
    member = api.make_member()
    item = api.make_item(name="Drill")
    api.rent(item["id"], member["id"])

    assert maintenance(api)["fleet"]["under_maintenance"] == 0

    assert api.post(f"/items/{item['id']}/maintenance", at=NOW).status_code == 200
    data = maintenance(api)
    assert (data["on_loan"], data["without_open_loan"]) == (1, 0)
    assert data["items"][0]["open_loan"]["due_at"] == "2026-10-19T10:00:00Z"

    assert api.post(f"/items/{item['id']}/return", at=NOW).status_code == 200
    data = maintenance(api)  # returned, but the item stays under maintenance
    assert (data["on_loan"], data["without_open_loan"]) == (0, 1)
    assert data["items"][0]["open_loan"] is None

    assert api.delete(f"/items/{item['id']}/maintenance", at=NOW).status_code == 200
    data = maintenance(api)
    assert data["fleet"]["under_maintenance"] == 0 and data["items"] == []
    assert data["fleet"]["available"] == 1


# --- the list is capped ------------------------------------------------------------------------


@pytest.mark.parametrize(("count", "truncated", "shown"), [(50, False, 50), (51, True, 50)])
def test_at_most_fifty_items_are_listed_and_the_total_stays_exact(
    api, session_factory, count, truncated, shown
):
    for number in range(count):
        new_item(session_factory, name=f"Item {number:03d}", status=BROKEN)

    data = maintenance(api)

    assert data["fleet"]["under_maintenance"] == count
    assert len(data["items"]) == shown and data["items_truncated"] is truncated
    assert [i["item_name"] for i in data["items"]] == [f"Item {n:03d}" for n in range(shown)]
    assert data["on_loan"] + data["without_open_loan"] == count
    assert sum(c["under_maintenance"] for c in data["by_category"]) == count


# --- documentation: there is no history --------------------------------------------------------


def test_the_response_says_there_is_no_maintenance_history(api):
    assert maintenance(api)["history_available"] is False

    spec = api.get("/openapi.json").json()
    schema = spec["components"]["schemas"]["MaintenanceRead"]
    assert "snapshot, not a history" in schema["description"]
    assert "never records when maintenance started or ended" in schema["description"]
    assert "none are inferred" in schema["description"]
    assert "Always false" in schema["properties"]["history_available"]["description"]
    path = spec["paths"]["/analytics/maintenance"]["get"]["description"]
    assert "never when maintenance started or ended" in path and "inferred" in path


def test_there_is_no_downtime_or_trend_field_to_misread(api):
    data = maintenance(api)

    assert set(data) == {
        "as_of",
        "history_available",
        "fleet",
        "share_of_fleet_pct",
        "on_loan",
        "on_loan_overdue",
        "without_open_loan",
        "by_category",
        "items",
        "items_truncated",
    }


# --- parameters, errors and conventions --------------------------------------------------------


def test_only_get_is_allowed_and_unknown_parameters_are_ignored(api):
    for method in ("post", "patch", "delete"):
        assert getattr(api, method)("/analytics/maintenance").status_code == 405
    assert maintenance(api, days=5, colour="red")["fleet"]["total_items"] == 0


@pytest.mark.parametrize("value", ["yesterday", "2026-10-12T10:00:00", "9999-12-31T23:59:59Z"])
def test_an_invalid_test_clock_is_a_400(api, value):
    response = api.get("/analytics/maintenance", at=None, headers={"X-Test-Clock": value})

    assert response.status_code == 400 and error_code(response) == "invalid_test_clock"


def test_without_a_test_clock_the_real_time_is_used(api):
    response = api.get("/analytics/maintenance", at=None)

    assert response.status_code == 200
    as_of = datetime.fromisoformat(response.json()["as_of"].replace("Z", "+00:00"))
    assert abs(datetime.now(UTC) - as_of) < timedelta(minutes=5)


def test_the_same_request_gives_the_same_answer_twice(api, workshop):
    assert maintenance(api) == maintenance(api)


# --- read-only and query count -----------------------------------------------------------------


def test_the_snapshot_changes_nothing_not_even_a_lapsed_hold(api, session_factory, workshop):
    reservation(
        session_factory,
        new_member(session_factory, name="Other"),
        new_item(session_factory, name="Lapsed"),
        NOW - 3 * DAY,
    )
    before = snapshot(session_factory)

    for at in (NOW, NOW + 3 * DAY, NOW - 30 * DAY):
        maintenance(api, at=at)

    assert snapshot(session_factory) == before
    assert any("reserved" in row for row in before["loans"])  # the lapsed hold is still saved


def test_only_read_statements_reach_the_database(api, session_factory, workshop):
    with captured_sql(session_factory) as statements:
        maintenance(api)

    verbs = {re.match(r"\s*(\w+)", statement).group(1).upper() for statement in statements}
    assert "SELECT" in verbs
    assert not verbs & {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "REPLACE"}


def test_the_number_of_queries_does_not_grow_with_the_amount_of_data(api, session_factory, member):
    new_item(session_factory, name="Only")

    def statements() -> int:
        with captured_sql(session_factory) as log:
            maintenance(api)
        return len(log)

    small = statements()
    for number in range(30):
        item = new_item(session_factory, name=f"Item {number}", category=f"Category {number % 4}")
        if number % 2:
            checked_out_loan(session_factory, member, item, NOW - number * HOUR, BROKEN)
        else:
            reservation(session_factory, member, item, NOW - HOUR, LoanStatus.CANCELLED)

    assert statements() == small
    assert small <= 5
