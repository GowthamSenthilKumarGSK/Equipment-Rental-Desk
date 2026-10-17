"""Reserve, check out, return, cancel and maintenance through the HTTP API."""

from datetime import timedelta

import pytest

from tests.api.conftest import DAY, LOAN_PERIOD, error_code
from tests.builders import NOW

HOUR = timedelta(hours=1)
SECOND = timedelta(seconds=1)


def item_status(api, item_id, at=NOW):
    return api.get(f"/items/{item_id}", at=at).json()["status"]


def test_full_rental_cycle(api):
    member, item = api.make_member(), api.make_item()

    reserved = api.reserve(item["id"], member["id"])
    assert reserved.status_code == 201
    loan = reserved.json()
    assert (loan["status"], loan["member_id"], loan["item_id"]) == (
        "reserved",
        member["id"],
        item["id"],
    )
    assert loan["reserved_at"] == "2026-10-12T10:00:00Z"
    assert loan["expires_at"] == "2026-10-14T10:00:00Z"
    assert item_status(api, item["id"]) == "reserved"

    checked_out = api.post(f"/items/{item['id']}/check-out", at=NOW + HOUR)
    assert checked_out.status_code == 200
    assert checked_out.json()["status"] == "checked_out"
    assert checked_out.json()["due_at"] == "2026-10-19T11:00:00Z"
    assert checked_out.json()["expires_at"] is None
    assert item_status(api, item["id"], NOW + HOUR) == "checked_out"

    returned = api.post(f"/items/{item['id']}/return", at=NOW + HOUR + LOAN_PERIOD)
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    assert returned.json()["fee_charged_paise"] == 0
    assert item_status(api, item["id"], NOW + 10 * DAY) == "available"


def test_late_return_charges_the_fee_to_the_balance(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])

    returned = api.post(f"/items/{item['id']}/return", at=NOW + LOAN_PERIOD + 2 * DAY + SECOND)

    assert returned.json()["fee_charged_paise"] == 3_000  # 2 days and a second late: 3 days
    assert api.get(f"/members/{member['id']}").json()["balance_paise"] == 3_000


def test_fee_is_capped_at_200_rupees_and_at_the_replacement_value(api):
    member = api.make_member()
    expensive, cheap = (
        api.make_item(name="Tiller"),
        api.make_item(name="Spirit level", replacement_value_paise=15_000),
    )
    api.rent(expensive["id"], member["id"])
    api.rent(cheap["id"], member["id"])
    late = NOW + LOAN_PERIOD + 30 * DAY

    assert (
        api.post(f"/items/{expensive['id']}/return", at=late).json()["fee_charged_paise"] == 20_000
    )
    assert api.post(f"/items/{cheap['id']}/return", at=late).json()["fee_charged_paise"] == 15_000


def test_cancel_reservation_frees_the_item(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    cancelled = api.delete(f"/items/{item['id']}/reservation", at=NOW + HOUR)

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] == "2026-10-12T11:00:00Z"
    assert item_status(api, item["id"]) == "available"


# --- missing things and malformed requests --------------------------------------------------


def test_unknown_item_or_member_is_404_on_every_action(api):
    member, item = api.make_member(), api.make_item()

    unknown_item = [
        api.reserve(999, member["id"]),
        api.delete("/items/999/reservation"),
        api.post("/items/999/check-out"),
        api.post("/items/999/return"),
        api.post("/items/999/maintenance"),
        api.delete("/items/999/maintenance"),
    ]
    unknown_member = api.reserve(item["id"], 999)

    for response in [*unknown_item, unknown_member]:
        assert response.status_code == 404, response.text
        assert error_code(response) == "not_found"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"member_id": "1"},
        {"member_id": 1.5},
        {"member_id": True},
        {"member_id": None},
        {"member_id": 0},
        {"member_id": -3},
        {"member_id": 2_147_483_648},
        {"member_id": 10**30},
        {"member_id": 1, "extra": 1},
    ],
)
def test_reserve_body_must_name_a_valid_member(api, body):
    item = api.make_item()

    response = api.post(f"/items/{item['id']}/reservation", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert item_status(api, item["id"]) == "available"


def test_reserve_without_a_body_is_a_validation_error(api):
    item = api.make_item()

    assert api.post(f"/items/{item['id']}/reservation").status_code == 422


@pytest.mark.parametrize("path", ["abc", "0", "-1", "99999999999999999999"])
def test_item_actions_reject_bad_ids(api, path):
    for response in (
        api.post(f"/items/{path}/check-out"),
        api.post(f"/items/{path}/return"),
        api.delete(f"/items/{path}/reservation"),
        api.post(f"/items/{path}/reservation", json={"member_id": 1}),
    ):
        assert response.status_code == 422
        assert error_code(response) == "validation_error"


# --- invalid transitions ---------------------------------------------------------------------


def test_cannot_reserve_an_item_that_is_not_available(api):
    first, second = api.make_member(), api.make_member(name="Second", phone="+91 00000 20002")
    item = api.make_item()
    api.reserve(item["id"], first["id"])

    response = api.reserve(item["id"], second["id"])

    assert (response.status_code, error_code(response)) == (409, "invalid_transition")
    assert "reserve" in response.json()["error"]["message"]


def test_cannot_check_out_without_a_reservation(api):
    item = api.make_item()

    response = api.post(f"/items/{item['id']}/check-out")

    assert (response.status_code, error_code(response)) == (409, "invalid_transition")


def test_double_check_out_is_refused_and_changes_nothing(api):
    member, item = api.make_member(), api.make_item()
    first = api.rent(item["id"], member["id"])

    second = api.post(f"/items/{item['id']}/check-out", at=NOW + DAY)

    assert (second.status_code, error_code(second)) == (409, "invalid_transition")
    assert (
        api.get(f"/items/{item['id']}", at=NOW + DAY).json()["current_loan"]["due_at"]
        == first["due_at"]
    )


def test_double_return_is_refused_and_charges_nothing_more(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])
    late = NOW + LOAN_PERIOD + 2 * DAY
    api.post(f"/items/{item['id']}/return", at=late)

    again = api.post(f"/items/{item['id']}/return", at=late + HOUR)

    assert (again.status_code, error_code(again)) == (409, "invalid_transition")
    assert api.get(f"/members/{member['id']}", at=late).json()["balance_paise"] == 2_000


def test_cannot_return_an_item_that_is_not_checked_out(api):
    member, item, other = api.make_member(), api.make_item(), api.make_item(name="Other")
    api.reserve(other["id"], member["id"])

    for item_id in (item["id"], other["id"]):
        response = api.post(f"/items/{item_id}/return")
        assert (response.status_code, error_code(response)) == (409, "invalid_transition")


def test_cancel_is_only_valid_for_a_reserved_loan(api):
    member, item, idle = api.make_member(), api.make_item(), api.make_item(name="Idle")
    api.rent(item["id"], member["id"])

    on_loan = api.delete(f"/items/{item['id']}/reservation")
    nothing_reserved = api.delete(f"/items/{idle['id']}/reservation")

    assert (on_loan.status_code, error_code(on_loan)) == (409, "invalid_transition")
    assert (nothing_reserved.status_code, error_code(nothing_reserved)) == (
        409,
        "invalid_transition",
    )


# --- reservation expiry ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("elapsed", "expected_status"),
    [
        (timedelta(hours=47, minutes=59), 200),
        (timedelta(hours=47, minutes=59, seconds=59), 200),
        (timedelta(hours=48), 409),
        (timedelta(hours=48, minutes=1), 409),
    ],
)
def test_check_out_at_the_expiry_boundary(api, elapsed, expected_status):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    response = api.post(f"/items/{item['id']}/check-out", at=NOW + elapsed)

    assert response.status_code == expected_status
    if expected_status == 409:
        assert error_code(response) == "reservation_expired"
        assert item_status(api, item["id"], NOW + elapsed) == "available"


def test_cancel_after_expiry_reports_expiry(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    response = api.delete(f"/items/{item['id']}/reservation", at=NOW + timedelta(hours=49))

    assert (response.status_code, error_code(response)) == (409, "reservation_expired")


def test_an_expired_reservation_frees_the_item_for_someone_else(api):
    first, second = api.make_member(), api.make_member(name="Second", phone="+91 00000 20002")
    item = api.make_item()
    api.reserve(item["id"], first["id"])
    later = NOW + timedelta(hours=48)

    assert api.reserve(item["id"], second["id"], at=later - SECOND).status_code == 409
    assert api.reserve(item["id"], second["id"], at=later).status_code == 201


# --- who may borrow --------------------------------------------------------------------------


def test_suspended_member_is_blocked_with_the_reason(api):
    member, item = api.make_member(), api.make_item()
    api.post(f"/members/{member['id']}/suspension")

    response = api.reserve(item["id"], member["id"])

    assert response.status_code == 403
    assert error_code(response) == "member_blocked"
    assert response.json()["error"]["details"] == {"reasons": ["suspended"]}
    assert item_status(api, item["id"]) == "available"


def test_member_blocked_after_reserving_cannot_check_out(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])
    api.post(f"/members/{member['id']}/suspension")

    response = api.post(f"/items/{item['id']}/check-out")

    assert (response.status_code, error_code(response)) == (403, "member_blocked")
    assert item_status(api, item["id"]) == "reserved"


@pytest.mark.parametrize(
    ("days_late", "blocked"),
    [(9, False), (10, False), (11, True)],  # fees of ₹90, exactly ₹100, ₹110
)
def test_unpaid_fees_over_100_rupees_block_reserving(api, days_late, blocked):
    member, borrowed, wanted = api.make_member(), api.make_item(), api.make_item(name="Wanted")
    api.rent(borrowed["id"], member["id"])
    api.post(f"/items/{borrowed['id']}/return", at=NOW + LOAN_PERIOD + days_late * DAY)
    when = NOW + LOAN_PERIOD + days_late * DAY

    response = api.reserve(wanted["id"], member["id"], at=when)

    if blocked:
        assert (response.status_code, error_code(response)) == (403, "member_blocked")
        assert response.json()["error"]["details"]["reasons"] == ["unpaid_fees"]
    else:
        assert response.status_code == 201


def test_paying_down_to_exactly_100_rupees_unblocks_the_member(api):
    member, borrowed, wanted = api.make_member(), api.make_item(), api.make_item(name="Wanted")
    api.rent(borrowed["id"], member["id"])
    when = NOW + LOAN_PERIOD + 11 * DAY
    api.post(f"/items/{borrowed['id']}/return", at=when)
    assert api.reserve(wanted["id"], member["id"], at=when).status_code == 403

    paid = api.post(f"/members/{member['id']}/payments", json={"amount_paise": 1_000}, at=when)

    assert paid.status_code == 201
    assert api.reserve(wanted["id"], member["id"], at=when).status_code == 201


@pytest.mark.parametrize(
    ("overdue_by", "blocked"),
    [(14 * DAY, False), (14 * DAY + SECOND, True)],
)
def test_loan_overdue_over_14_days_blocks_reserving(api, overdue_by, blocked):
    member, held, wanted = api.make_member(), api.make_item(), api.make_item(name="Wanted")
    api.rent(held["id"], member["id"])
    when = NOW + LOAN_PERIOD + overdue_by

    response = api.reserve(wanted["id"], member["id"], at=when)

    if blocked:
        assert (response.status_code, error_code(response)) == (403, "member_blocked")
        assert response.json()["error"]["details"]["reasons"] == ["long_overdue"]
    else:
        assert response.status_code == 201


def test_fourth_active_loan_is_refused(api):
    member = api.make_member()
    items = [api.make_item(name=f"Item {n}") for n in range(4)]
    for item in items[:3]:
        assert api.reserve(item["id"], member["id"]).status_code == 201

    response = api.reserve(items[3]["id"], member["id"])

    assert response.status_code == 403
    assert error_code(response) == "loan_limit_exceeded"
    assert api.get(f"/members/{member['id']}").json()["active_loan_count"] == 3


# --- maintenance -----------------------------------------------------------------------------


def test_maintenance_round_trip(api):
    item = api.make_item()

    started = api.post(f"/items/{item['id']}/maintenance")
    assert (started.status_code, started.json()["status"]) == (200, "under_maintenance")
    again = api.post(f"/items/{item['id']}/maintenance")
    assert (again.status_code, error_code(again)) == (409, "invalid_transition")

    finished = api.delete(f"/items/{item['id']}/maintenance")
    assert (finished.status_code, finished.json()["status"]) == (200, "available")
    not_in_maintenance = api.delete(f"/items/{item['id']}/maintenance")
    assert (not_in_maintenance.status_code, error_code(not_in_maintenance)) == (
        409,
        "invalid_transition",
    )


def test_an_item_under_maintenance_cannot_be_reserved(api):
    member, item = api.make_member(), api.make_item()
    api.post(f"/items/{item['id']}/maintenance")

    assert api.reserve(item["id"], member["id"]).status_code == 409


def test_maintenance_cancels_a_reservation_but_keeps_it_as_history(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    api.post(f"/items/{item['id']}/maintenance")

    statement = api.get(f"/members/{member['id']}/statement").json()
    assert [loan["status"] for loan in statement["loans"]] == ["cancelled"]


def test_returning_an_item_sent_to_maintenance_does_not_make_it_available(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])
    during = api.post(f"/items/{item['id']}/maintenance")
    assert during.json()["status"] == "under_maintenance"
    assert during.json()["current_loan"]["status"] == "checked_out"

    refused = api.delete(f"/items/{item['id']}/maintenance", at=NOW + DAY)
    assert (refused.status_code, error_code(refused)) == (409, "invalid_transition")

    api.post(f"/items/{item['id']}/return", at=NOW + 2 * DAY)
    assert item_status(api, item["id"], NOW + 2 * DAY) == "under_maintenance"
    assert (
        api.delete(f"/items/{item['id']}/maintenance", at=NOW + 2 * DAY).json()["status"]
        == "available"
    )
