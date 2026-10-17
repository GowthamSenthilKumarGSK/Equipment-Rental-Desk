import pytest

from tests.api.conftest import DAY, LOAN_PERIOD, error_code
from tests.builders import NOW


def owe(api, member_id, fee_paise_days):
    """Give the member a balance by returning an item `fee_paise_days` days late (₹10 a day)."""
    item = api.make_item(name=f"Item owing {fee_paise_days} days")
    api.rent(item["id"], member_id)
    api.post(f"/items/{item['id']}/return", at=NOW + LOAN_PERIOD + fee_paise_days * DAY)


def balance(api, member_id, at=NOW + 30 * DAY):
    return api.get(f"/members/{member_id}", at=at).json()["balance_paise"]


def test_payment_is_recorded_and_reduces_the_balance(api):
    member = api.make_member()
    owe(api, member["id"], 12)  # ₹120

    response = api.post(
        f"/members/{member['id']}/payments", json={"amount_paise": 4_500, "note": "UPI"}
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["member_id"], body["amount_paise"], body["note"]) == (member["id"], 4_500, "UPI")
    assert body["paid_at"] == "2026-10-12T10:00:00Z"
    assert balance(api, member["id"]) == 12_000 - 4_500


def test_payment_equal_to_the_balance_clears_it(api):
    member = api.make_member()
    owe(api, member["id"], 12)

    response = api.post(f"/members/{member['id']}/payments", json={"amount_paise": 12_000})

    assert response.status_code == 201
    assert balance(api, member["id"]) == 0


def test_overpayment_is_rejected_and_not_recorded(api):
    member = api.make_member()
    owe(api, member["id"], 12)

    response = api.post(f"/members/{member['id']}/payments", json={"amount_paise": 12_001})

    assert response.status_code == 422
    assert error_code(response) == "payment_exceeds_balance"
    assert "₹120.01" in response.json()["error"]["message"]
    statement = api.get(f"/members/{member['id']}/statement", at=NOW + 30 * DAY).json()
    assert statement["payments"] == []
    assert statement["balance_paise"] == 12_000


def test_any_payment_is_rejected_when_nothing_is_owed(api):
    member = api.make_member()

    response = api.post(f"/members/{member['id']}/payments", json={"amount_paise": 100})

    assert (response.status_code, error_code(response)) == (422, "payment_exceeds_balance")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"amount_paise": 0},
        {"amount_paise": -100},
        {"amount_paise": 10.5},
        {"amount_paise": 100.0},
        {"amount_paise": "100"},
        {"amount_paise": True},
        {"amount_paise": None},
        {"amount_paise": 10**30},
        {"amount_paise": 100, "note": "x" * 201},
        {"amount_paise": 100, "currency": "USD"},
    ],
)
def test_malformed_payment_is_refused(api, body):
    member = api.make_member()
    owe(api, member["id"], 12)

    response = api.post(f"/members/{member['id']}/payments", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert balance(api, member["id"]) == 12_000


def test_payment_for_an_unknown_member_is_404(api):
    response = api.post("/members/999/payments", json={"amount_paise": 100})

    assert (response.status_code, error_code(response)) == (404, "not_found")
    assert api.post("/members/0/payments", json={"amount_paise": 100}).status_code == 422


def test_a_suspended_member_can_still_pay(api):
    member = api.make_member()
    owe(api, member["id"], 5)
    api.post(f"/members/{member['id']}/suspension")

    assert (
        api.post(f"/members/{member['id']}/payments", json={"amount_paise": 500}).status_code == 201
    )


# --- statement -------------------------------------------------------------------------------


def test_statement_of_a_new_member_is_empty(api):
    member = api.make_member()

    statement = api.get(f"/members/{member['id']}/statement").json()

    assert statement == {
        "member": member,
        "balance_paise": 0,
        "total_fees_paise": 0,
        "total_payments_paise": 0,
        "active_loan_count": 0,
        "block_reasons": [],
        "at_loan_limit": False,
        "loans": [],
        "payments": [],
    }


def test_statement_unknown_member_is_404(api):
    response = api.get("/members/999/statement")

    assert (response.status_code, error_code(response)) == (404, "not_found")


def test_statement_shows_loans_fees_payments_and_balance(api):
    member = api.make_member()
    returned_late, still_out, lapsed = (
        api.make_item(name="Returned late"),
        api.make_item(name="Still out"),
        api.make_item(name="Lapsed"),
    )
    api.rent(returned_late["id"], member["id"])  # at NOW, due NOW + 7d
    api.post(f"/items/{returned_late['id']}/return", at=NOW + LOAN_PERIOD + 2 * DAY)  # 2 days: ₹20
    day10 = NOW + 10 * DAY
    api.rent(still_out["id"], member["id"], at=day10)  # due day 17
    api.reserve(lapsed["id"], member["id"], at=day10)  # hold ends day 12
    api.post(
        f"/members/{member['id']}/payments", json={"amount_paise": 500, "note": "Cash"}, at=day10
    )
    when = NOW + 19 * DAY  # "Still out" is 2 days overdue; the reservation lapsed days ago

    statement = api.get(f"/members/{member['id']}/statement", at=when).json()

    assert statement["balance_paise"] == 1_500  # ₹20 fee - ₹5 paid
    assert statement["total_fees_paise"] == 2_000
    assert statement["total_payments_paise"] == 500
    assert statement["active_loan_count"] == 1  # the lapsed reservation no longer counts
    assert statement["block_reasons"] == []

    # Newest first: the day-10 loans (reserved, then checked out), then the one returned late.
    rows = [
        (r["item_name"], r["status"], r["is_overdue"], r["days_overdue"])
        for r in statement["loans"]
    ]
    assert rows == [
        ("Lapsed", "expired", False, 0),
        ("Still out", "checked_out", True, 2),
        ("Returned late", "returned", False, 0),
    ]
    by_name = {r["item_name"]: r["loan"] for r in statement["loans"]}
    assert by_name["Returned late"]["fee_charged_paise"] == 2_000
    assert by_name["Still out"]["fee_charged_paise"] == 0  # charged only when returned
    assert [(p["amount_paise"], p["note"]) for p in statement["payments"]] == [(500, "Cash")]


def test_statement_lists_payments_newest_first(api):
    member = api.make_member()
    owe(api, member["id"], 10)
    for amount, day in [(100, 20), (200, 21), (300, 22)]:
        api.post(
            f"/members/{member['id']}/payments", json={"amount_paise": amount}, at=NOW + day * DAY
        )

    statement = api.get(f"/members/{member['id']}/statement", at=NOW + 30 * DAY).json()

    assert [p["amount_paise"] for p in statement["payments"]] == [300, 200, 100]
    assert statement["balance_paise"] == 10_000 - 600


def test_statement_explains_why_a_member_is_blocked(api):
    member = api.make_member()
    owe(api, member["id"], 11)
    api.post(f"/members/{member['id']}/suspension")

    statement = api.get(f"/members/{member['id']}/statement", at=NOW + 30 * DAY).json()

    assert set(statement["block_reasons"]) == {"suspended", "unpaid_fees"}
