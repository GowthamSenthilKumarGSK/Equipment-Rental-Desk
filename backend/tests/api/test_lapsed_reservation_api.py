"""An item whose hold has run out is shown the way the member statement shows that loan.

The item then reads as available and has no current loan. The stored loan row is not touched by a
read, and it still appears (as expired) in the member's history.
"""

from datetime import timedelta

from tests.builders import NOW

HOLD = timedelta(hours=48)
JUST_BEFORE = HOLD - timedelta(minutes=1)
JUST_AFTER = HOLD + timedelta(minutes=1)


def reserve_one(api):
    member, item = api.make_member(), api.make_item()
    loan = api.reserve(item["id"], member["id"]).json()
    return member, item, loan


def test_just_before_the_hold_ends_the_item_is_still_reserved_with_its_loan(api):
    member, item, loan = reserve_one(api)

    detail = api.get(f"/items/{item['id']}", at=NOW + JUST_BEFORE).json()

    assert detail["status"] == "reserved"
    assert detail["current_loan"]["id"] == loan["id"]
    assert detail["current_loan"]["status"] == "reserved"


def test_at_exactly_48_hours_the_item_is_available_and_has_no_current_loan(api):
    member, item, loan = reserve_one(api)

    detail = api.get(f"/items/{item['id']}", at=NOW + HOLD).json()

    assert detail["status"] == "available"
    assert detail["current_loan"] is None
    assert detail["allowed_actions"] == ["reserve", "start_maintenance"]


def test_after_the_hold_ends_the_item_is_available_and_has_no_current_loan(api):
    member, item, loan = reserve_one(api)

    detail = api.get(f"/items/{item['id']}", at=NOW + JUST_AFTER).json()

    assert detail["status"] == "available"
    assert detail["current_loan"] is None


def test_the_item_list_agrees_with_the_item_detail(api):
    member, item, loan = reserve_one(api)

    for offset, expected_status, has_loan in [
        (JUST_BEFORE, "reserved", True),
        (HOLD, "available", False),
        (JUST_AFTER, "available", False),
    ]:
        listed = api.get("/items", at=NOW + offset).json()["results"][0]
        assert listed["status"] == expected_status
        assert (listed["current_loan"] is not None) is has_loan


def test_the_member_statement_and_the_item_agree_at_every_point_of_the_boundary(api):
    member, item, loan = reserve_one(api)

    for offset, loan_status in [
        (JUST_BEFORE, "reserved"),
        (HOLD, "expired"),
        (JUST_AFTER, "expired"),
    ]:
        at = NOW + offset
        statement = api.get(f"/members/{member['id']}/statement", at=at).json()
        detail = api.get(f"/items/{item['id']}", at=at).json()

        assert statement["loans"][0]["status"] == loan_status
        assert (detail["current_loan"] is not None) is (loan_status == "reserved")


def test_history_is_kept_and_reading_does_not_change_it(api):
    member, item, loan = reserve_one(api)

    api.get(f"/items/{item['id']}", at=NOW + JUST_AFTER)  # a read after the hold ended
    api.get("/items", at=NOW + JUST_AFTER)

    # A read earlier in time still sees the reservation: nothing was written by the reads above.
    earlier = api.get(f"/items/{item['id']}", at=NOW + JUST_BEFORE).json()
    assert earlier["current_loan"]["status"] == "reserved"
    statement = api.get(f"/members/{member['id']}/statement", at=NOW + JUST_AFTER).json()
    assert [row["loan"]["id"] for row in statement["loans"]] == [loan["id"]]
    assert statement["loans"][0]["status"] == "expired"


def test_after_the_hold_ends_someone_else_can_reserve_and_becomes_the_current_loan(api):
    first, item, loan = reserve_one(api)
    second = api.make_member(name="Dev Kapoor", phone="+91 00000 20002")
    later = NOW + JUST_AFTER

    response = api.reserve(item["id"], second["id"], at=later)

    assert response.status_code == 201
    detail = api.get(f"/items/{item['id']}", at=later).json()
    assert detail["status"] == "reserved"
    assert detail["current_loan"]["member_id"] == second["id"]
    first_statement = api.get(f"/members/{first['id']}/statement", at=later).json()
    assert first_statement["loans"][0]["status"] == "expired"  # history kept
