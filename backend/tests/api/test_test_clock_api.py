"""The reviewer's X-Test-Clock header."""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings, get_settings
from tests.api.conftest import error_code
from tests.builders import NOW


def test_the_header_sets_now_and_utc_is_what_comes_back(api):
    member, item = api.make_member(), api.make_item()

    # The same instant written in IST, in UTC with Z, and with an explicit +00:00.
    for header in (
        "2026-10-15T15:30:00+05:30",
        "2026-10-15T10:00:00Z",
        "2026-10-15T10:00:00+00:00",
    ):
        api.delete(f"/items/{item['id']}/reservation", headers={"X-Test-Clock": header}, at=None)
        response = api.post(
            f"/items/{item['id']}/reservation",
            json={"member_id": member["id"]},
            headers={"X-Test-Clock": header},
            at=None,
        )
        assert response.status_code == 201, response.text
        assert response.json()["reserved_at"] == "2026-10-15T10:00:00Z"
        assert response.json()["expires_at"] == "2026-10-17T10:00:00Z"
        api.delete(f"/items/{item['id']}/reservation", headers={"X-Test-Clock": header}, at=None)


def test_without_the_header_the_real_clock_is_used(api):
    member, item = api.make_member(), api.make_item()
    before = datetime.now(UTC)

    response = api.post(
        f"/items/{item['id']}/reservation", json={"member_id": member["id"]}, at=None
    )

    after = datetime.now(UTC)
    reserved_at = datetime.fromisoformat(response.json()["reserved_at"])
    assert before - timedelta(seconds=1) <= reserved_at <= after + timedelta(seconds=1)
    assert reserved_at.year >= 2026


def test_each_request_has_its_own_clock(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])  # at NOW

    late = api.post(f"/items/{item['id']}/check-out", at=NOW + timedelta(hours=49))
    early = api.post(f"/items/{item['id']}/check-out", at=NOW + timedelta(hours=1))

    assert (late.status_code, error_code(late)) == (409, "reservation_expired")
    # The late attempt saved the expiry, so the reservation is gone even for an earlier clock.
    assert early.status_code == 409


def test_moving_the_clock_forward_makes_a_loan_overdue_without_waiting(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])

    on_time = api.get(f"/items/{item['id']}", at=NOW + timedelta(days=6)).json()["status"]
    late = api.get(f"/items/{item['id']}", at=NOW + timedelta(days=8)).json()["status"]

    assert (on_time, late) == ("checked_out", "overdue")


@pytest.mark.parametrize(
    "value",
    [
        "garbage",
        "",
        "   ",
        "2026-10-12",  # a date alone has no time or zone
        "2026-10-12T10:00:00",  # no UTC offset: ambiguous, so refused
        "2026-13-45T10:00:00Z",
        "12/10/2026 10:00",
        "1760263200",  # a Unix timestamp is not ISO-8601
        "tomorrow",
    ],
)
def test_invalid_header_values_are_refused_without_running_the_request(api, value):
    member, item = api.make_member(), api.make_item()

    response = api.post(
        f"/items/{item['id']}/reservation",
        json={"member_id": member["id"]},
        headers={"X-Test-Clock": value},
        at=None,
    )

    assert response.status_code == 400
    assert error_code(response) == "invalid_test_clock"
    assert "ISO-8601" in response.json()["error"]["message"]
    assert api.get(f"/items/{item['id']}").json()["status"] == "available"


# --- the accepted range: 2000-01-01 to 2200-01-01 (UTC) ---------------------------------------

OUT_OF_RANGE = [
    "9999-12-31T23:59:59Z",  # a reservation made then used to be committed, then break every read
    "0001-01-01T00:00:00+05:30",  # converting to UTC used to overflow
    "9999-12-31T23:59:59-05:00",
    "0001-01-01T00:00:00Z",
    "1999-12-31T23:59:59Z",  # one second before the range
    "2000-01-01T00:00:00+05:30",  # = 1999-12-31T18:30Z, so before the range
    "2200-01-01T00:00:01Z",  # one second after the range
]
IN_RANGE = [
    "2000-01-01T00:00:00Z",  # the first accepted instant
    "2000-01-01T05:30:00+05:30",  # the same instant, written in IST
    "2026-10-12T10:00:00Z",
    "2199-12-31T23:59:59Z",
    "2200-01-01T00:00:00Z",  # the last accepted instant
]


@pytest.mark.parametrize("value", OUT_OF_RANGE)
def test_out_of_range_clock_is_refused_before_anything_is_written(api, value, caplog):
    caplog.set_level("DEBUG", logger="app")
    member, item = api.make_member(), api.make_item()
    headers = {"X-Test-Clock": value}

    refused = [
        api.post(
            f"/items/{item['id']}/reservation",
            json={"member_id": member["id"]},
            headers=headers,
            at=None,
        ),
        api.post(
            "/members",
            json={"name": "Never Created", "phone": "+91 00000 99999"},
            headers=headers,
            at=None,
        ),
        api.post(
            f"/members/{member['id']}/payments",
            json={"amount_paise": 100},
            headers=headers,
            at=None,
        ),
        api.post(f"/items/{item['id']}/maintenance", headers=headers, at=None),
        api.get("/items", headers=headers, at=None),
        api.get(f"/members/{member['id']}/statement", headers=headers, at=None),
        api.get("/loans/overdue", headers=headers, at=None),
    ]

    for response in refused:
        assert response.status_code == 400, response.text
        assert error_code(response) == "invalid_test_clock"
        assert "between 2000-01-01 and 2200-01-01" in response.json()["error"]["message"]
    # Nothing was written by any of those requests ...
    assert api.get("/members").json()["total"] == 1
    assert api.get(f"/members/{member['id']}/statement").json()["loans"] == []
    assert api.get(f"/items/{item['id']}").json()["status"] == "available"
    # ... and the app carries on as normal.
    assert api.get("/items").status_code == 200
    assert api.reserve(item["id"], member["id"]).status_code == 201
    assert value not in "".join(record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("value", OUT_OF_RANGE)
def test_existing_reservations_stay_usable_after_a_refused_clock(api, value):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    refused_check_out = api.post(
        f"/items/{item['id']}/check-out", headers={"X-Test-Clock": value}, at=None
    )
    refused_cancel = api.delete(
        f"/items/{item['id']}/reservation", headers={"X-Test-Clock": value}, at=None
    )

    assert refused_check_out.status_code == refused_cancel.status_code == 400
    assert (
        api.post(f"/items/{item['id']}/check-out", at=NOW + timedelta(hours=1)).status_code == 200
    )
    assert api.post(f"/items/{item['id']}/return", at=NOW + timedelta(days=2)).status_code == 200


@pytest.mark.parametrize("value", IN_RANGE)
def test_clocks_inside_the_range_are_accepted(api, value):
    response = api.get("/items", headers={"X-Test-Clock": value}, at=None)

    assert response.status_code == 200, response.text


def test_a_whole_rental_works_at_the_far_end_of_the_range(api):
    """Adding 48 hours or 7 days or a late fee to a time near 2200 cannot overflow."""
    member, item = api.make_member(), api.make_item()
    start = datetime(2199, 12, 20, tzinfo=UTC)

    reserved = api.reserve(item["id"], member["id"], at=start)
    checked_out = api.post(f"/items/{item['id']}/check-out", at=start + timedelta(days=1))
    returned = api.post(f"/items/{item['id']}/return", at=datetime(2200, 1, 1, tzinfo=UTC))

    assert reserved.json()["expires_at"] == "2199-12-22T00:00:00Z"
    assert checked_out.json()["due_at"] == "2199-12-28T00:00:00Z"
    assert returned.status_code == 200
    assert returned.json()["fee_charged_paise"] == 4_000  # 3 days 24 hours late is 4 days
    assert api.get("/loans/overdue", at=datetime(2200, 1, 1, tzinfo=UTC)).json()["total"] == 0


def test_a_whole_rental_works_at_the_near_end_of_the_range(api):
    member, item = api.make_member(), api.make_item()
    start = datetime(2000, 1, 1, tzinfo=UTC)

    assert api.reserve(item["id"], member["id"], at=start).status_code == 201
    assert (
        api.post(f"/items/{item['id']}/check-out", at=start + timedelta(hours=1)).status_code == 200
    )
    assert api.post(f"/items/{item['id']}/return", at=start + timedelta(days=9)).status_code == 200


def test_the_header_can_be_switched_off(api):
    api.client.app.dependency_overrides[get_settings] = lambda: Settings(allow_test_clock=False)
    try:
        refused = api.get("/items", at=NOW)
        allowed = api.get("/items", at=None)
    finally:
        api.client.app.dependency_overrides.clear()

    assert (refused.status_code, error_code(refused)) == (400, "test_clock_disabled")
    assert allowed.status_code == 200


@pytest.mark.parametrize("value", [*OUT_OF_RANGE, *IN_RANGE, "garbage"])
def test_when_switched_off_every_header_value_is_refused_and_nothing_is_written(api, value):
    api.client.app.dependency_overrides[get_settings] = lambda: Settings(allow_test_clock=False)
    try:
        refused = api.post(
            "/members",
            json={"name": "Never Created", "phone": "+91 00000 99999"},
            headers={"X-Test-Clock": value},
            at=None,
        )
        created_without_header = api.post(
            "/members", json={"name": "Created", "phone": "+91 00000 99998"}, at=None
        )
    finally:
        api.client.app.dependency_overrides.clear()

    assert (refused.status_code, error_code(refused)) == (400, "test_clock_disabled")
    assert created_without_header.status_code == 201
    assert [m["name"] for m in api.get("/members").json()["results"]] == ["Created"]


def test_the_header_is_documented_in_the_openapi_schema(api):
    schema = api.get("/openapi.json", at=None).json()

    parameters = schema["paths"]["/items/{item_id}/check-out"]["post"]["parameters"]
    header = next(p for p in parameters if p["name"] == "x-test-clock")
    assert header["in"] == "header"
    assert "ISO-8601" in header["description"]
    assert "2000-01-01 and 2200-01-01" in header["description"]
    assert "X-Test-Clock" in schema["info"]["description"]
