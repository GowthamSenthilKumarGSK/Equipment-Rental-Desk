from datetime import timedelta

import pytest

from tests.api.conftest import DAY, LOAN_PERIOD, error_code
from tests.builders import NOW

SECOND = timedelta(seconds=1)


def overdue(api, at, query=""):
    response = api.get(f"/loans/overdue{query}", at=at)
    assert response.status_code == 200, response.text
    return response.json()


def test_nothing_is_overdue_on_an_empty_library(api):
    assert overdue(api, NOW) == {"results": [], "total": 0, "limit": 50, "offset": 0}


def test_a_loan_is_overdue_only_after_its_due_time(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])
    due = NOW + LOAN_PERIOD

    assert overdue(api, due - SECOND)["total"] == 0
    assert overdue(api, due)["total"] == 0  # exactly at the due time is still on time
    assert overdue(api, due + SECOND)["total"] == 1


def test_overdue_entry_has_everything_the_desk_needs(api):
    member = api.make_member(name="Rohan Das", phone="+91 00000 30002")
    item = api.make_item(name="Garden Tiller", replacement_value_paise=1_800_000)
    api.rent(item["id"], member["id"])

    result = overdue(api, NOW + LOAN_PERIOD + 2 * DAY + SECOND)

    [row] = result["results"]
    assert row["member_id"] == member["id"]
    assert (row["member_name"], row["member_phone"]) == ("Rohan Das", "+91 00000 30002")
    assert (row["item_id"], row["item_name"]) == (item["id"], "Garden Tiller")
    assert row["checked_out_at"] == "2026-10-12T10:00:00Z"
    assert row["due_at"] == "2026-10-19T10:00:00Z"
    assert row["days_overdue"] == 3  # 2 days and a second: rounded up
    assert row["fee_if_returned_now_paise"] == 3_000


def test_fee_so_far_respects_both_caps(api):
    member = api.make_member()
    big, cheap = (
        api.make_item(name="Big"),
        api.make_item(name="Cheap", replacement_value_paise=15_000),
    )
    api.rent(big["id"], member["id"])
    api.rent(cheap["id"], member["id"])

    rows = {r["item_name"]: r for r in overdue(api, NOW + LOAN_PERIOD + 40 * DAY)["results"]}

    assert rows["Big"]["fee_if_returned_now_paise"] == 20_000
    assert rows["Cheap"]["fee_if_returned_now_paise"] == 15_000
    assert rows["Big"]["days_overdue"] == 40


def test_returned_and_reserved_loans_are_not_listed(api):
    member = api.make_member()
    returned, reserved, out = (api.make_item(name=n) for n in ("Returned", "Reserved", "Out"))
    api.rent(returned["id"], member["id"])
    api.post(f"/items/{returned['id']}/return", at=NOW + DAY)
    api.reserve(reserved["id"], member["id"])
    api.rent(out["id"], member["id"])

    names = [r["item_name"] for r in overdue(api, NOW + LOAN_PERIOD + DAY)["results"]]

    assert names == ["Out"]


def test_most_overdue_first_and_paginated(api):
    items = [api.make_item(name=f"Item {n}") for n in range(3)]
    members = [api.make_member(name=f"Member {n}", phone=f"+91 00000 4000{n}") for n in range(3)]
    # Checked out on days 3, 1 and 2, so due-order is item 1, item 2, item 0.
    for item, member, day in zip(items, members, (3, 1, 2), strict=True):
        api.rent(item["id"], member["id"], at=NOW + day * DAY)
    when = NOW + 20 * DAY

    everything = overdue(api, when)
    assert [r["item_name"] for r in everything["results"]] == ["Item 1", "Item 2", "Item 0"]

    second_page = overdue(api, when, "?limit=1&offset=1")
    assert [r["item_name"] for r in second_page["results"]] == ["Item 2"]
    assert (second_page["total"], second_page["limit"], second_page["offset"]) == (3, 1, 1)


def test_an_overdue_loan_on_an_item_in_maintenance_is_still_listed(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])
    api.post(f"/items/{item['id']}/maintenance")

    assert overdue(api, NOW + LOAN_PERIOD + DAY)["total"] == 1


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=201", "offset=-1", "limit=x", "offset=99999999999999999999"]
)
def test_bad_overdue_parameters_are_refused(api, query):
    response = api.get(f"/loans/overdue?{query}")

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
