from datetime import timedelta

import pytest

from tests.api.conftest import LOAN_PERIOD, error_code
from tests.builders import NOW

HOUR = timedelta(hours=1)


def test_create_item_starts_available(api):
    response = api.post(
        "/items",
        json={"name": " Step Ladder ", "category": "Ladders", "replacement_value_paise": 280_000},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "name": "Step Ladder",
        "category": "Ladders",
        "replacement_value_paise": 280_000,
        "condition_note": "",
        "status": "available",
        "current_loan": None,
    }


def test_create_item_keeps_the_condition_note(api):
    item = api.make_item(condition_note="Left grip taped")

    assert item["condition_note"] == "Left grip taped"


@pytest.mark.parametrize(
    ("overrides", "bad_field"),
    [
        ({"name": ""}, "name"),
        ({"name": "x" * 101}, "name"),
        ({"category": "  "}, "category"),
        ({"replacement_value_paise": 0}, "replacement_value_paise"),
        ({"replacement_value_paise": -100}, "replacement_value_paise"),
        ({"replacement_value_paise": 12.5}, "replacement_value_paise"),
        ({"replacement_value_paise": 1200.0}, "replacement_value_paise"),
        ({"replacement_value_paise": "1200"}, "replacement_value_paise"),
        ({"replacement_value_paise": True}, "replacement_value_paise"),
        ({"replacement_value_paise": None}, "replacement_value_paise"),
        ({"replacement_value_paise": 100_000_001}, "replacement_value_paise"),
        ({"replacement_value_paise": 10**30}, "replacement_value_paise"),
        ({"condition_note": "x" * 1001}, "condition_note"),
        ({"status": "available"}, "status"),
    ],
)
def test_invalid_item_is_refused_with_the_field_named(api, overrides, bad_field):
    body = {"name": "Drill", "category": "Power Tools", "replacement_value_paise": 650_000}

    response = api.post("/items", json=body | overrides)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    fields = [detail["field"] for detail in response.json()["error"]["details"]]
    assert any(field.endswith(bad_field) for field in fields), fields


def test_missing_fields_are_all_reported(api):
    response = api.post("/items", json={})

    fields = {detail["field"] for detail in response.json()["error"]["details"]}
    assert fields == {"body.name", "body.category", "body.replacement_value_paise"}


def test_get_item_and_unknown_item(api):
    item = api.make_item()

    assert api.get(f"/items/{item['id']}").json() == item
    missing = api.get("/items/999")
    assert (missing.status_code, error_code(missing)) == (404, "not_found")
    assert api.get("/items/0").status_code == 422
    assert api.get("/items/abc").status_code == 422
    assert api.get("/items/99999999999999999999").status_code == 422


def test_update_item_changes_only_what_is_sent_and_never_the_status(api):
    item = api.make_item(name="Drill", category="Power Tools")

    response = api.patch(
        f"/items/{item['id']}",
        json={"replacement_value_paise": 700_000, "condition_note": "New battery"},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["replacement_value_paise"], body["condition_note"]) == (
        "Drill",
        700_000,
        "New battery",
    )
    assert body["status"] == "available"


def test_condition_note_can_be_cleared(api):
    item = api.make_item(condition_note="Scratched")

    assert (
        api.patch(f"/items/{item['id']}", json={"condition_note": ""}).json()["condition_note"]
        == ""
    )


@pytest.mark.parametrize(
    "body",
    [{}, {"name": None}, {"name": ""}, {"replacement_value_paise": 0}, {"status": "reserved"}],
)
def test_invalid_item_update_is_refused(api, body):
    item = api.make_item()

    response = api.patch(f"/items/{item['id']}", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_update_unknown_item_is_404(api):
    assert api.patch("/items/999", json={"name": "X"}).status_code == 404


def test_delete_item_without_history(api):
    item = api.make_item()

    assert api.delete(f"/items/{item['id']}").status_code == 204
    assert api.get(f"/items/{item['id']}").status_code == 404
    assert api.delete(f"/items/{item['id']}").status_code == 404


def test_item_with_loan_history_cannot_be_deleted(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])
    api.delete(f"/items/{item['id']}/reservation")  # even a cancelled reservation is history

    response = api.delete(f"/items/{item['id']}")

    assert (response.status_code, error_code(response)) == (409, "deletion_blocked")
    assert api.get(f"/items/{item['id']}").status_code == 200


# --- listing ---------------------------------------------------------------------------------


def test_list_items_is_paginated_and_sorted_by_name(api):
    for name in ["Saw", "Ladder", "Drill", "Tiller"]:
        api.make_item(name=name)

    page = api.get("/items?limit=3&offset=1").json()

    assert [i["name"] for i in page["results"]] == ["Ladder", "Saw", "Tiller"]
    assert (page["total"], page["limit"], page["offset"]) == (4, 3, 1)


def test_list_items_filters_by_category_and_name(api):
    api.make_item(name="Cordless Drill", category="Power Tools")
    api.make_item(name="Extension Ladder", category="Ladders")
    api.make_item(name="Step Ladder", category="Ladders")

    assert api.get("/items?category=ladders").json()["total"] == 2
    assert [i["name"] for i in api.get("/items?q=drill").json()["results"]] == ["Cordless Drill"]
    assert api.get("/items?category=ladders&q=step").json()["total"] == 1
    assert api.get("/items?q=%25").json()["total"] == 0  # a literal %, not a wildcard


def test_list_status_filter_reflects_expiry_and_overdue_at_the_request_time(api):
    member = api.make_member()
    reserved, rented, free = (api.make_item(name=n) for n in ("Reserved", "Rented", "Free"))
    api.reserve(reserved["id"], member["id"])
    api.rent(rented["id"], member["id"])

    def names(status, at):
        response = api.get(f"/items?status={status}", at=at)
        assert response.status_code == 200
        return sorted(i["name"] for i in response.json()["results"])

    just_before_expiry = NOW + timedelta(hours=47, minutes=59)
    assert names("reserved", just_before_expiry) == ["Reserved"]
    assert names("available", just_before_expiry) == ["Free"]

    at_expiry = NOW + timedelta(hours=48)  # the hold has lapsed, with no background job involved
    assert names("reserved", at_expiry) == []
    assert names("available", at_expiry) == ["Free", "Reserved"]

    assert names("checked_out", NOW + LOAN_PERIOD) == ["Rented"]  # exactly due: still on time
    assert names("overdue", NOW + LOAN_PERIOD) == []
    assert names("overdue", NOW + LOAN_PERIOD + timedelta(seconds=1)) == ["Rented"]
    assert names("checked_out", NOW + LOAN_PERIOD + timedelta(seconds=1)) == []


def test_status_filter_counts_and_paginates_the_filtered_list(api):
    for n in range(5):
        api.make_item(name=f"Item {n}")
    maintenance = api.make_item(name="Broken")
    api.post(f"/items/{maintenance['id']}/maintenance")

    page = api.get("/items?status=available&limit=2&offset=4").json()

    assert page["total"] == 5
    assert [i["name"] for i in page["results"]] == ["Item 4"]
    assert api.get("/items?status=under_maintenance").json()["total"] == 1


@pytest.mark.parametrize(
    "query", ["status=lost", "limit=0", "limit=201", "offset=-1", "offset=99999999999999999999"]
)
def test_bad_item_list_parameters_are_refused(api, query):
    response = api.get(f"/items?{query}")

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_item_detail_shows_the_current_loan(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    detail = api.get(f"/items/{item['id']}", at=NOW + HOUR).json()

    assert detail["status"] == "reserved"
    assert detail["current_loan"]["member_id"] == member["id"]
    assert detail["current_loan"]["status"] == "reserved"
