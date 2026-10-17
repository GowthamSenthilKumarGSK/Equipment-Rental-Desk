from datetime import UTC, datetime

import pytest

from tests.api.conftest import error_code


def test_create_member_returns_the_new_member(api):
    response = api.post("/members", json={"name": "  Asha Rao ", "phone": "+91 00000 20001"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Asha Rao"  # surrounding spaces are trimmed
    assert body["phone"] == "+91 00000 20001"
    assert body["status"] == "active"
    assert body["join_date"] == "2026-10-12"
    assert isinstance(body["id"], int)


def test_join_date_defaults_to_the_current_date_in_ist_not_utc(api):
    late_evening_utc = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)  # already 13 October in IST

    response = api.post(
        "/members", json={"name": "Asha", "phone": "+91 00000 20001"}, at=late_evening_utc
    )

    assert response.json()["join_date"] == "2026-10-13"


def test_join_date_can_be_given(api):
    body = {"name": "Asha", "phone": "+91 00000 20001", "join_date": "2025-01-31"}

    assert api.post("/members", json=body).json()["join_date"] == "2025-01-31"


@pytest.mark.parametrize(
    ("body", "bad_field"),
    [
        ({"phone": "+91 00000 20001"}, "name"),
        ({"name": "Asha"}, "phone"),
        ({"name": "", "phone": "+91 00000 20001"}, "name"),
        ({"name": "   ", "phone": "+91 00000 20001"}, "name"),
        ({"name": "x" * 101, "phone": "+91 00000 20001"}, "name"),
        ({"name": 123, "phone": "+91 00000 20001"}, "name"),
        ({"name": None, "phone": "+91 00000 20001"}, "name"),
        ({"name": "Asha", "phone": "not a number"}, "phone"),
        ({"name": "Asha", "phone": "123"}, "phone"),
        ({"name": "Asha", "phone": "9" * 21}, "phone"),
        ({"name": "Asha", "phone": 919876543210}, "phone"),
        ({"name": "Asha", "phone": "+91 00000 20001", "join_date": "2026-13-45"}, "join_date"),
        ({"name": "Asha", "phone": "+91 00000 20001", "status": "suspended"}, "status"),
    ],
)
def test_invalid_member_is_refused_with_the_field_named(api, body, bad_field):
    response = api.post("/members", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    fields = [detail["field"] for detail in response.json()["error"]["details"]]
    assert any(field.endswith(bad_field) for field in fields), fields


@pytest.mark.parametrize("payload", [[], "text", 5, None])
def test_body_must_be_a_json_object(api, payload):
    response = api.post("/members", json=payload)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_malformed_json_is_a_400_not_a_crash(api):
    response = api.post(
        "/members", content='{"name": "Asha", ', headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert error_code(response) == "malformed_json"


def test_get_member_includes_balance_and_block_reasons(api):
    member = api.make_member()

    response = api.get(f"/members/{member['id']}")

    assert response.status_code == 200
    assert response.json() == {
        **member,
        "balance_paise": 0,
        "active_loan_count": 0,
        "block_reasons": [],
    }


def test_unknown_member_is_404(api):
    response = api.get("/members/999")

    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert "Member 999" in response.json()["error"]["message"]


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "0", "-1", "2147483648", "99999999999999999999"])
def test_member_id_must_be_a_positive_32_bit_integer(api, bad_id):
    """Out-of-range ids are refused up front; they would otherwise overflow the database driver."""
    response = api.get(f"/members/{bad_id}")

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_the_largest_valid_id_is_simply_not_found(api):
    assert api.get("/members/2147483647").status_code == 404


def test_list_members_is_paginated_and_sorted_by_name(api):
    for name in ["Eve", "Dan", "Cara", "Ben", "Amy"]:
        api.make_member(name=name)

    first = api.get("/members?limit=2&offset=0").json()
    second = api.get("/members?limit=2&offset=2").json()

    assert [m["name"] for m in first["results"]] == ["Amy", "Ben"]
    assert [m["name"] for m in second["results"]] == ["Cara", "Dan"]
    assert (first["total"], first["limit"], first["offset"]) == (5, 2, 0)
    assert second["offset"] == 2


def test_list_members_filters_by_search_and_status(api):
    api.make_member(name="Priya Nair", phone="+91 00000 30001")
    other = api.make_member(name="Rohan Das", phone="+91 00000 30002")
    api.post(f"/members/{other['id']}/suspension")

    assert [m["name"] for m in api.get("/members?q=priya").json()["results"]] == ["Priya Nair"]
    assert [m["name"] for m in api.get("/members?q=30002").json()["results"]] == ["Rohan Das"]
    suspended = api.get("/members?status=suspended").json()
    assert [m["name"] for m in suspended["results"]] == ["Rohan Das"]
    assert api.get("/members?status=active").json()["total"] == 1


def test_search_text_is_not_treated_as_a_wildcard(api):
    api.make_member(name="Priya Nair")

    assert api.get("/members?q=%25").json()["total"] == 0  # a literal % matches nothing
    assert api.get("/members?q=_riya").json()["total"] == 0


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=201", "limit=abc", "offset=-1", "status=banned", "q=" + "x" * 101]
)
def test_bad_list_parameters_are_refused(api, query):
    response = api.get(f"/members?{query}")

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_update_member_changes_only_what_is_sent(api):
    member = api.make_member(name="Asha Rao", phone="+91 00000 20001")

    response = api.patch(f"/members/{member['id']}", json={"phone": "+91 00000 20009"})

    assert response.status_code == 200
    assert response.json()["phone"] == "+91 00000 20009"
    assert response.json()["name"] == "Asha Rao"


@pytest.mark.parametrize(
    "body",
    [{}, {"name": None}, {"name": ""}, {"phone": "abc"}, {"status": "suspended"}, {"id": 5}],
)
def test_invalid_member_update_is_refused(api, body):
    member = api.make_member()

    response = api.patch(f"/members/{member['id']}", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_update_unknown_member_is_404(api):
    assert api.patch("/members/999", json={"name": "X"}).status_code == 404


def test_delete_member_without_history(api):
    member = api.make_member()

    assert api.delete(f"/members/{member['id']}").status_code == 204
    assert api.get(f"/members/{member['id']}").status_code == 404
    assert api.delete(f"/members/{member['id']}").status_code == 404


def test_member_with_history_cannot_be_deleted(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    response = api.delete(f"/members/{member['id']}")

    assert response.status_code == 409
    assert error_code(response) == "deletion_blocked"
    assert api.get(f"/members/{member['id']}").status_code == 200


def test_suspend_and_reinstate(api):
    member = api.make_member()

    suspended = api.post(f"/members/{member['id']}/suspension", json={"reason": "Damaged tool"})
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert api.get(f"/members/{member['id']}").json()["block_reasons"] == ["suspended"]

    reinstated = api.delete(f"/members/{member['id']}/suspension")
    assert reinstated.json()["status"] == "active"
    assert api.get(f"/members/{member['id']}").json()["block_reasons"] == []


def test_suspending_needs_no_body(api):
    member = api.make_member()

    assert api.post(f"/members/{member['id']}/suspension").json()["status"] == "suspended"


def test_suspension_errors(api):
    member = api.make_member()

    not_suspended = api.delete(f"/members/{member['id']}/suspension")
    assert (not_suspended.status_code, error_code(not_suspended)) == (409, "invalid_transition")

    api.post(f"/members/{member['id']}/suspension")
    again = api.post(f"/members/{member['id']}/suspension")
    assert (again.status_code, error_code(again)) == (409, "invalid_transition")

    too_long = api.post(f"/members/{member['id']}/suspension", json={"reason": "x" * 201})
    assert too_long.status_code == 422
    assert api.post("/members/999/suspension").status_code == 404
    assert api.delete("/members/999/suspension").status_code == 404
