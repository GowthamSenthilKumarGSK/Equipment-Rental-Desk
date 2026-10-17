"""Text that PostgreSQL cannot store is refused up front with a 422, not left to the database.

PostgreSQL text columns cannot hold the NUL character (U+0000); SQLite can, so without these checks
the problem would only show up in production. These tests run on SQLite, where the character would
otherwise have been stored, so a 422 here proves the API refuses it rather than the database.
"""

import pytest

from tests.api.conftest import error_code

NUL_NAME = "Asha\u0000Rao"


def assert_refused_for_nul(response, field_suffix: str):
    assert response.status_code == 422, response.text
    assert error_code(response) == "validation_error"
    details = response.json()["error"]["details"]
    assert any(d["field"].endswith(field_suffix) and "NUL" in d["message"] for d in details), (
        details
    )


@pytest.mark.parametrize("field", ["name", "phone"])
def test_member_text_with_nul_is_refused_and_not_stored(api, field):
    body = {"name": "Asha Rao", "phone": "+91 00000 20001"} | {
        field: NUL_NAME if field == "name" else "+91 000\u000000 20001"
    }

    response = api.post("/members", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert api.get("/members").json()["total"] == 0


def test_member_name_nul_message_is_explicit(api):
    assert_refused_for_nul(
        api.post("/members", json={"name": NUL_NAME, "phone": "+91 00000 20001"}), "name"
    )


def test_member_update_with_nul_is_refused_and_changes_nothing(api):
    member = api.make_member(name="Asha Rao")

    response = api.patch(f"/members/{member['id']}", json={"name": NUL_NAME})

    assert_refused_for_nul(response, "name")
    assert api.get(f"/members/{member['id']}").json()["name"] == "Asha Rao"


def test_suspension_reason_with_nul_is_refused_and_the_member_is_not_suspended(api):
    member = api.make_member()

    response = api.post(f"/members/{member['id']}/suspension", json={"reason": "bad\u0000reason"})

    assert_refused_for_nul(response, "reason")
    assert api.get(f"/members/{member['id']}").json()["status"] == "active"


def test_payment_note_with_nul_is_refused_before_the_balance_is_even_looked_at(api):
    member = api.make_member()

    response = api.post(
        f"/members/{member['id']}/payments", json={"amount_paise": 100, "note": "Cash\u0000"}
    )

    assert_refused_for_nul(response, "note")


@pytest.mark.parametrize("field", ["name", "category", "condition_note"])
def test_item_text_with_nul_is_refused_and_not_stored(api, field):
    body = {"name": "Drill", "category": "Tools", "replacement_value_paise": 650_000}
    body[field] = f"bad\u0000{field}"

    response = api.post("/items", json=body)

    assert_refused_for_nul(response, field)
    assert api.get("/items").json()["total"] == 0


@pytest.mark.parametrize("field", ["name", "category", "condition_note"])
def test_item_update_with_nul_is_refused_and_changes_nothing(api, field):
    item = api.make_item(name="Drill", category="Tools", condition_note="Fine")

    response = api.patch(f"/items/{item['id']}", json={field: f"bad\u0000{field}"})

    assert_refused_for_nul(response, field)
    assert api.get(f"/items/{item['id']}").json() == item


@pytest.mark.parametrize(
    ("path", "param"),
    [("/members", "q"), ("/items", "q"), ("/items", "category")],
)
def test_search_text_with_nul_is_refused(api, path, param):
    response = api.get(path, params={param: "a\u0000b"})

    assert_refused_for_nul(response, param)


def test_nul_escaped_in_the_url_is_refused_too(api):
    response = api.get("/members?q=a%00b")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "text",
    [
        "Asha \U0001f600",
        "அசோக் குமார்",
        "Zoë Müller",
        "tab\tinside",
        'O\'Brien "Bob" <b>&amp;</b>',
    ],
)
def test_ordinary_unicode_and_punctuation_are_still_accepted(api, text):
    response = api.post("/members", json={"name": text, "phone": "+91 00000 20001"})

    assert response.status_code == 201, response.text
    assert response.json()["name"] == text.strip()
