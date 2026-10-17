"""`at_loan_limit` tells a UI that a member cannot reserve another item, without the UI knowing 3.

It is not a block reason: the limit stops reserving only (A15), so a member who is at the limit
can still check out a reservation they already hold.
"""

from datetime import timedelta

from tests.builders import NOW


def hold(api, member, count):
    """Give `member` `count` more reserved items; returns the items."""
    items = [api.make_item(name=f"Tool {n}") for n in range(count)]
    for item in items:
        assert api.reserve(item["id"], member["id"]).status_code == 201
    return items


def flags(api, member, at=NOW):
    detail = api.get(f"/members/{member['id']}", at=at).json()
    statement = api.get(f"/members/{member['id']}/statement", at=at).json()
    assert detail["at_loan_limit"] == statement["at_loan_limit"]
    assert detail["active_loan_count"] == statement["active_loan_count"]
    assert detail["block_reasons"] == statement["block_reasons"]
    return statement["active_loan_count"], statement["at_loan_limit"], statement["block_reasons"]


def test_the_limit_is_reached_at_exactly_three_active_loans(api):
    member = api.make_member()

    assert flags(api, member) == (0, False, [])
    hold(api, member, 1)
    assert flags(api, member) == (1, False, [])
    hold(api, member, 1)
    assert flags(api, member) == (2, False, [])
    hold(api, member, 1)
    assert flags(api, member) == (3, True, [])  # at the limit, yet no block reason


def test_a_fourth_reservation_is_refused_exactly_when_the_flag_is_set(api):
    member = api.make_member()
    hold(api, member, 2)
    spare = api.make_item(name="Spare")

    assert flags(api, member)[1] is False
    assert api.reserve(spare["id"], member["id"]).status_code == 201

    assert flags(api, member)[1] is True
    another = api.make_item(name="One too many")
    refused = api.reserve(another["id"], member["id"])
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "loan_limit_exceeded"


def test_a_lapsed_reservation_no_longer_counts(api):
    member = api.make_member()
    hold(api, member, 3)

    assert flags(api, member, at=NOW + timedelta(hours=47, minutes=59))[1] is True
    assert flags(api, member, at=NOW + timedelta(hours=48)) == (0, False, [])


def test_cancelling_or_returning_frees_a_place(api):
    member = api.make_member()
    first, second, third = hold(api, member, 3)

    assert api.delete(f"/items/{first['id']}/reservation").status_code == 200
    assert flags(api, member) == (2, False, [])

    assert api.reserve(first["id"], member["id"]).status_code == 201
    assert api.post(f"/items/{second['id']}/check-out").status_code == 200
    assert flags(api, member)[1] is True  # a checked-out loan counts too
    assert api.post(f"/items/{second['id']}/return").status_code == 200
    assert flags(api, member) == (2, False, [])


def test_being_at_the_limit_does_not_stop_checking_out_a_held_reservation(api):
    member = api.make_member()
    items = hold(api, member, 3)

    assert flags(api, member)[1] is True
    assert api.post(f"/items/{items[0]['id']}/check-out").status_code == 200


def test_the_flag_is_independent_of_the_block_reasons(api):
    member = api.make_member()
    hold(api, member, 3)
    api.post(f"/members/{member['id']}/suspension", json={})

    assert flags(api, member) == (3, True, ["suspended"])
    api.delete(f"/members/{member['id']}/suspension")
    assert flags(api, member) == (3, True, [])
