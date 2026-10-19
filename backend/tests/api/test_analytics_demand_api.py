"""GET /analytics/demand: the reservation funnel, demand by category and the most reserved items."""

from datetime import timedelta

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
MICRO = timedelta(microseconds=1)
HOLD = timedelta(hours=48)
# NOW is 15:30 IST on Mon 12 Oct 2026. A 7-day report starts 6 Oct 00:00 IST; the matching point of
# the week before is NOW minus 7 days, and that week starts 29 Sep 00:00 IST.
CURRENT_START = NOW.replace(hour=0, minute=0) - timedelta(days=6) - timedelta(hours=5, minutes=30)
PREVIOUS_START = CURRENT_START - 7 * DAY
MATCHING_POINT = NOW - 7 * DAY

EMPTY_FUNNEL = {
    "reserved": 0,
    "checked_out": 0,
    "returned": 0,
    "cancelled": 0,
    "expired": 0,
    "still_held": 0,
    "conversion_rate_pct": None,
}


def demand(api, **params):
    return fetch(api, "demand", **params)


@pytest.fixture
def member(session_factory):
    return new_member(session_factory, name="Borrower")


def made_and_collected(session_factory, member, item, reserved_at, *, back=True):
    """A reservation that became a loan an hour later (returned two days after that, if `back`)."""
    checked_out_at = reserved_at + HOUR
    if back:
        returned_loan(
            session_factory,
            member,
            item,
            due_at=checked_out_at + 7 * DAY,
            returned_at=checked_out_at + 2 * DAY,
            checked_out_at=checked_out_at,
        )
    else:
        checked_out_loan(session_factory, member, item, checked_out_at + 7 * DAY)


# --- an empty library --------------------------------------------------------------------------


def test_without_items_or_reservations_everything_is_zero_and_null(api):
    data = demand(api)

    assert data["reservations"] == {"current": 0, "previous": 0, "change_pct": None}
    assert data["funnel"] == data["previous_funnel"] == EMPTY_FUNNEL
    assert data["categories"] == []
    assert data["top_items"] == []


def test_items_nobody_reserved_are_listed_by_category_but_not_as_top_items(api, session_factory):
    new_item(session_factory, category="Tools")
    new_item(session_factory, name="Tent", category="Camping")

    data = demand(api)

    assert data["categories"] == [
        {
            "category": "Camping",
            "items": 1,
            "reservations": 0,
            "checked_out": 0,
            "share_pct": None,
            "reservations_per_item": 0.0,
        },
        {
            "category": "Tools",
            "items": 1,
            "reservations": 0,
            "checked_out": 0,
            "share_pct": None,
            "reservations_per_item": 0.0,
        },
    ]
    assert data["top_items"] == []


# --- the funnel --------------------------------------------------------------------------------


@pytest.fixture
def busy_week(session_factory, member):
    """Reservations of every outcome made in the last 7 days, and two the week before."""
    drill = new_item(session_factory, name="Drill", category="Power Tools")
    saw = new_item(session_factory, name="Saw", category="Power Tools")
    mower = new_item(session_factory, name="Mower", category="Garden")
    rake = new_item(session_factory, name="Rake", category="garden")
    new_item(session_factory, name="Tent", category="Camping")

    made_and_collected(session_factory, member, drill, NOW - 5 * DAY)  # handed over, returned
    made_and_collected(session_factory, member, drill, NOW - 2 * DAY, back=False)  # still out
    reservation(session_factory, member, saw, NOW - 3 * DAY, LoanStatus.CANCELLED)
    reservation(session_factory, member, saw, NOW - 4 * DAY, LoanStatus.EXPIRED)  # saved as expired
    reservation(session_factory, member, mower, NOW - 3 * DAY)  # lapsed, never saved as expired
    reservation(session_factory, member, rake, NOW - HOUR)  # waiting, hold running

    # The previous week: one handed over, one cancelled, and two that the comparison leaves out
    # because they were made after the matching point of that week.
    made_and_collected(session_factory, member, drill, PREVIOUS_START + DAY)
    reservation(session_factory, member, saw, PREVIOUS_START + 2 * DAY, LoanStatus.CANCELLED)
    reservation(session_factory, member, saw, MATCHING_POINT + MICRO, LoanStatus.CANCELLED)
    reservation(session_factory, member, saw, CURRENT_START - MICRO, LoanStatus.CANCELLED)
    return {"drill": drill, "saw": saw, "mower": mower, "rake": rake}


def test_the_funnel_accounts_for_every_reservation_exactly_once(api, busy_week):
    funnel = demand(api, days=7)["funnel"]

    assert funnel == {
        "reserved": 6,
        "checked_out": 2,
        "returned": 1,
        "cancelled": 1,
        "expired": 2,  # the one saved as expired and the one whose hold simply ran out
        "still_held": 1,
        "conversion_rate_pct": 40.0,  # 2 of the 5 that have been settled
    }
    assert funnel["reserved"] == sum(
        funnel[key] for key in ("checked_out", "cancelled", "expired", "still_held")
    )


def test_the_previous_funnel_covers_only_the_matching_part_of_last_week(api, busy_week):
    data = demand(api, days=7)

    assert data["previous_funnel"] == {
        "reserved": 2,
        "checked_out": 1,
        "returned": 1,
        "cancelled": 1,
        "expired": 0,
        "still_held": 0,
        "conversion_rate_pct": 50.0,
    }
    assert data["reservations"] == {"current": 6, "previous": 2, "change_pct": 200.0}
    assert data["window"]["previous_through"] == "2026-10-05T10:00:00Z"


def test_the_demand_count_is_the_reservation_count_of_the_summary(api, busy_week):
    summary = fetch(api, "summary", days=7)["reservations_created"]

    assert demand(api, days=7)["reservations"] == summary


def test_the_period_edges_are_exact(api, session_factory, member):
    for number, moment in enumerate(
        [
            CURRENT_START,  # first instant of the report: counted
            CURRENT_START - MICRO,  # last instant before it: the previous week
            NOW,  # exactly now: counted
            NOW + SECOND,  # not made yet
        ]
    ):
        item = new_item(session_factory, name=f"Item {number}")
        reservation(session_factory, member, item, moment, LoanStatus.CANCELLED)

    data = demand(api, days=7)

    assert data["funnel"]["reserved"] == 2
    assert data["reservations"]["previous"] == 0  # CURRENT_START - 1µs is later than NOW - 7 days


def test_a_hold_expires_in_the_funnel_exactly_when_the_item_endpoint_says_so(
    api, session_factory, member
):
    item = new_item(session_factory)
    reservation(session_factory, member, item, NOW)

    for moment, state, held, expired in [
        (NOW + HOLD - MICRO, "reserved", 1, 0),
        (NOW + HOLD, "available", 0, 1),
        (NOW + HOLD + SECOND, "available", 0, 1),
    ]:
        funnel = demand(api, days=7, at=moment)["funnel"]
        assert api.get(f"/items/{item}", at=moment).json()["status"] == state
        assert (funnel["still_held"], funnel["expired"]) == (held, expired), moment


def test_a_reservation_cancelled_or_collected_after_now_has_not_happened_yet(
    api, session_factory, member
):
    cancelled_later = new_item(session_factory, name="Cancelled later")
    reservation(session_factory, member, cancelled_later, NOW, LoanStatus.CANCELLED)  # at NOW + 1h
    collected_later = new_item(session_factory, name="Collected later")
    made_and_collected(session_factory, member, collected_later, NOW - 30 * 60 * SECOND)

    at_now = demand(api, days=1)["funnel"]
    later = demand(api, days=1, at=NOW + HOUR)["funnel"]

    assert (at_now["cancelled"], at_now["checked_out"], at_now["still_held"]) == (0, 0, 2)
    assert (later["cancelled"], later["checked_out"], later["still_held"]) == (1, 1, 0)


def test_the_conversion_rate_ignores_reservations_still_waiting(api, session_factory, member):
    made_and_collected(session_factory, member, new_item(session_factory), NOW - 6 * HOUR)
    reservation(session_factory, member, new_item(session_factory, name="Waiting"), NOW - HOUR)

    funnel = demand(api, days=1)["funnel"]

    assert (funnel["reserved"], funnel["still_held"]) == (2, 1)
    assert funnel["conversion_rate_pct"] == 100.0


def test_a_reservation_cancelled_for_maintenance_looks_like_any_other_cancellation(api):
    member = api.make_member()
    item = api.make_item()
    assert api.reserve(item["id"], member["id"]).status_code == 201
    assert api.post(f"/items/{item['id']}/maintenance", at=NOW).status_code == 200

    funnel = demand(api)["funnel"]

    assert (funnel["reserved"], funnel["cancelled"]) == (1, 1)  # the reason is not recorded
    assert demand(api)["top_items"][0]["current_status"] == "under_maintenance"


def test_a_funnel_built_through_the_api_matches_what_was_done(api):
    member = api.make_member()
    first, second, third, fourth = (api.make_item(name=f"Item {n}") for n in range(4))
    api.rent(first["id"], member["id"], at=NOW - 3 * DAY)
    assert api.post(f"/items/{first['id']}/return", at=NOW - 2 * DAY).status_code == 200
    api.rent(second["id"], member["id"], at=NOW - 2 * DAY)
    assert api.reserve(third["id"], member["id"], at=NOW - DAY).status_code == 201
    assert api.delete(f"/items/{third['id']}/reservation", at=NOW - DAY + HOUR).status_code == 200
    assert api.reserve(fourth["id"], member["id"], at=NOW - HOUR).status_code == 201

    funnel = demand(api, days=7)["funnel"]

    assert funnel == {
        "reserved": 4,
        "checked_out": 2,
        "returned": 1,
        "cancelled": 1,
        "expired": 0,
        "still_held": 1,
        "conversion_rate_pct": 66.7,
    }


# --- categories and top items ------------------------------------------------------------------


def test_demand_by_category_groups_names_without_regard_to_case(api, busy_week):
    categories = demand(api, days=7)["categories"]

    assert categories == [
        {
            "category": "Power Tools",
            "items": 2,
            "reservations": 4,
            "checked_out": 2,
            "share_pct": 66.7,
            "reservations_per_item": 2.0,
        },
        {
            "category": "Garden",  # "Garden" and "garden" are one category
            "items": 2,
            "reservations": 2,
            "checked_out": 0,
            "share_pct": 33.3,
            "reservations_per_item": 1.0,
        },
        {
            "category": "Camping",
            "items": 1,
            "reservations": 0,
            "checked_out": 0,
            "share_pct": 0.0,
            "reservations_per_item": 0.0,
        },
    ]
    assert sum(c["reservations"] for c in categories) == demand(api, days=7)["funnel"]["reserved"]
    assert sum(c["items"] for c in categories) == api.get("/items", at=NOW).json()["total"]


def test_top_items_are_ranked_by_reservations_then_handovers_then_id(api, busy_week):
    top = demand(api, days=7)["top_items"]

    assert [(t["item_name"], t["reservations"], t["checked_out"]) for t in top] == [
        ("Drill", 2, 2),
        ("Saw", 2, 0),
        ("Mower", 1, 0),
        ("Rake", 1, 0),
    ]  # the tent was never reserved
    assert top[0]["category"] == "Power Tools"


def test_top_items_show_the_status_the_items_endpoint_shows(api, busy_week):
    top = demand(api, days=7)["top_items"]

    statuses = {t["item_name"]: t["current_status"] for t in top}
    assert statuses == {
        "Drill": "checked_out",
        "Saw": "available",
        "Mower": "available",  # its hold ran out, although the row still says reserved
        "Rake": "reserved",
    }
    for entry in top:
        assert (
            api.get(f"/items/{entry['item_id']}", at=NOW).json()["status"]
            == (entry["current_status"])
        )
    assert {t["current_status"] for t in top} <= set(ItemStatus)


def test_with_equal_reservations_the_item_that_was_collected_more_ranks_first(
    api, session_factory, member
):
    ignored = new_item(session_factory, name="Ignored")  # the lower id, but never collected
    popular = new_item(session_factory, name="Popular")
    reservation(session_factory, member, ignored, NOW - 3 * HOUR, LoanStatus.CANCELLED)
    made_and_collected(session_factory, member, popular, NOW - 5 * HOUR)

    top = demand(api, days=1)["top_items"]

    assert [(t["item_name"], t["reservations"], t["checked_out"]) for t in top] == [
        ("Popular", 1, 1),
        ("Ignored", 1, 0),
    ]


def test_only_five_top_items_are_listed(api, session_factory, member):
    for number in range(7):
        item = new_item(session_factory, name=f"Item {number}")
        reservation(session_factory, member, item, NOW - number * HOUR, LoanStatus.CANCELLED)

    top = demand(api, days=7)["top_items"]

    assert [t["item_id"] for t in top] == sorted(t["item_id"] for t in top)  # equal counts: by id
    assert len(top) == 5


def test_reservations_of_the_previous_week_do_not_make_an_item_a_top_item(
    api, session_factory, member
):
    item = new_item(session_factory)
    reservation(session_factory, member, item, PREVIOUS_START + DAY, LoanStatus.CANCELLED)

    assert demand(api, days=7)["top_items"] == []


# --- documentation -----------------------------------------------------------------------------


def test_the_openapi_states_what_demand_cannot_know(api):
    schemas = api.get("/openapi.json").json()["components"]["schemas"]

    assert "cannot be measured" in schemas["DemandRead"]["description"]
    cancelled = schemas["FunnelRead"]["properties"]["cancelled"]["description"]
    assert "maintenance" in cancelled and "does not record why" in cancelled
    assert "48-hour" in schemas["FunnelRead"]["properties"]["expired"]["description"]


# --- stored-expired reservations under a backward clock -----------------------------------------


def test_a_reservation_stored_as_expired_is_still_held_at_a_clock_before_its_hold_ran_out(
    api, session_factory, member
):
    item = new_item(session_factory)
    made = NOW - 3 * DAY
    reservation(session_factory, member, item, made, LoanStatus.EXPIRED)  # saved as expired

    for moment, held, expired in [
        (made + HOUR, 1, 0),  # the funnel judges the timestamps, not the stored word
        (made + HOLD - MICRO, 1, 0),
        (made + HOLD, 0, 1),  # the hold runs out at exactly 48 hours
        (NOW, 0, 1),
    ]:
        funnel = demand(api, days=7, at=moment)["funnel"]
        assert (funnel["reserved"], funnel["still_held"], funnel["expired"]) == (
            1,
            held,
            expired,
        ), moment
        # No other bucket is involved.
        assert funnel["checked_out"] == funnel["cancelled"] == 0


def test_the_item_endpoint_reads_the_stored_row_so_it_never_shows_that_item_as_reserved(
    api, session_factory, member
):
    """Pinned on purpose: an expired row is not an active loan, so the item is available at any
    clock, while the funnel (which reads the timestamps) calls the reservation 'held' until the
    hold has run out."""
    item = new_item(session_factory)
    made = NOW - 3 * DAY
    reservation(session_factory, member, item, made, LoanStatus.EXPIRED)
    early = made + HOUR

    assert api.get(f"/items/{item}", at=early).json()["status"] == "available"
    assert demand(api, days=7, at=early)["funnel"]["still_held"] == 1


# --- category order -----------------------------------------------------------------------------


def test_categories_with_equal_demand_are_ordered_by_name_ignoring_case(
    api, session_factory, member
):
    for number, category in enumerate(["Zebra", "apple", "Mango"]):
        item = new_item(session_factory, name=f"Item {number}", category=category)
        reservation(session_factory, member, item, NOW - HOUR, LoanStatus.CANCELLED)
    new_item(session_factory, name="Idle zoo", category="Zoo")
    new_item(session_factory, name="Idle bird", category="bird")

    categories = [c["category"] for c in demand(api)["categories"]]

    assert categories == ["apple", "Mango", "Zebra", "bird", "Zoo"]


def test_more_demand_ranks_before_the_name(api, session_factory, member):
    for category, count in [("apple", 1), ("Zebra", 2)]:
        for copy in range(count):
            item = new_item(session_factory, name=f"{category} {copy}", category=category)
            reservation(session_factory, member, item, NOW - HOUR, LoanStatus.CANCELLED)

    assert [c["category"] for c in demand(api)["categories"]] == ["Zebra", "apple"]


def test_demand_groups_categories_exactly_as_the_items_filter_does(api, session_factory, member):
    for number, category in enumerate(["Café", "CAFé", "café", "École", "ÉCOLE", "école"]):
        item = new_item(session_factory, name=f"Item {number}", category=category)
        reservation(session_factory, member, item, NOW - HOUR, LoanStatus.CANCELLED)

    categories = demand(api)["categories"]

    for label in ("café", "école"):
        exact = [c for c in categories if c["category"] == label]
        group = (exact or [c for c in categories if c["category"].casefold() == label])[0]
        assert (
            group["items"] == api.get(f"/items?category={label}&limit=50", at=NOW).json()["total"]
        )
        assert group["reservations"] == group["items"]  # one reservation per item
    assert sum(c["items"] for c in categories) == 6


# --- documentation ------------------------------------------------------------------------------


def test_the_openapi_says_the_previous_funnel_is_not_maturity_adjusted(api):
    schemas = api.get("/openapi.json").json()["components"]["schemas"]

    previous = schemas["DemandRead"]["properties"]["previous_funnel"]["description"]
    assert "judged at `as_of`" in previous and "longer to be settled" in previous
    rate = schemas["FunnelRead"]["properties"]["conversion_rate_pct"]["description"]
    assert "maturity-adjusted" in rate
    assert (
        "maturity-adjusted"
        in api.get("/openapi.json").json()["paths"]["/analytics/demand"]["get"]["description"]
    )
    category = schemas["CategoryDemandRead"]["properties"]["category"]["description"]
    assert "lower()" in category and "ASCII" in category
