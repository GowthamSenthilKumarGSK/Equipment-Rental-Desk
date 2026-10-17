"""`allowed_actions` tells a UI which buttons to show, so it never has to know the item rules."""

from datetime import timedelta

import pytest

from tests.api.conftest import DAY, LOAN_PERIOD
from tests.builders import NOW


def actions(api, item_id, at=NOW):
    return api.get(f"/items/{item_id}", at=at).json()["allowed_actions"]


def test_an_available_item_can_be_reserved_or_sent_to_maintenance(api):
    item = api.make_item()

    assert actions(api, item["id"]) == ["reserve", "start_maintenance"]


def test_a_reserved_item_can_be_checked_out_cancelled_or_sent_to_maintenance(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    assert actions(api, item["id"]) == ["check_out", "cancel_reservation", "start_maintenance"]


def test_a_lapsed_reservation_offers_the_actions_of_an_available_item(api):
    member, item = api.make_member(), api.make_item()
    api.reserve(item["id"], member["id"])

    assert actions(api, item["id"], at=NOW + timedelta(hours=47, minutes=59)) == [
        "check_out",
        "cancel_reservation",
        "start_maintenance",
    ]
    assert actions(api, item["id"], at=NOW + timedelta(hours=48)) == [
        "reserve",
        "start_maintenance",
    ]


def test_a_checked_out_or_overdue_item_can_be_returned_or_sent_to_maintenance(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])

    assert actions(api, item["id"]) == ["return", "start_maintenance"]
    assert actions(api, item["id"], at=NOW + LOAN_PERIOD + DAY) == ["return", "start_maintenance"]


def test_an_item_under_maintenance_can_only_be_released(api):
    item = api.make_item()
    api.post(f"/items/{item['id']}/maintenance")

    assert actions(api, item["id"]) == ["finish_maintenance"]


def test_an_item_sent_to_maintenance_while_on_loan_can_only_be_returned(api):
    member, item = api.make_member(), api.make_item()
    api.rent(item["id"], member["id"])
    api.post(f"/items/{item['id']}/maintenance")

    assert actions(api, item["id"]) == ["return"]
    api.post(f"/items/{item['id']}/return", at=NOW + DAY)
    assert actions(api, item["id"], at=NOW + DAY) == ["finish_maintenance"]


# --- the list and the real endpoints agree -----------------------------------------------------
#
# For every state an item can be in, try every staff action through the API on a fresh item. An
# action in `allowed_actions` must succeed; one that is not listed must be refused with 409 and
# change nothing. So the buttons a UI draws from the list always match what the endpoints do.

LATE = NOW + LOAN_PERIOD + DAY


def _under_maintenance_on_loan(api, item_id, member_id):
    api.rent(item_id, member_id)
    assert api.post(f"/items/{item_id}/maintenance").status_code == 200


def _under_maintenance_idle(api, item_id, member_id):
    assert api.post(f"/items/{item_id}/maintenance").status_code == 200


# state name -> (arrange the state on a fresh item, the moment to try the actions at)
STATES = {
    "available": (lambda api, item, member: None, NOW),
    "reserved": (lambda api, item, member: api.reserve(item, member), NOW),
    "checked_out": (lambda api, item, member: api.rent(item, member), NOW),
    "overdue": (lambda api, item, member: api.rent(item, member), LATE),
    "under_maintenance_on_loan": (_under_maintenance_on_loan, NOW),
    "under_maintenance_idle": (_under_maintenance_idle, NOW),
}

ACTIONS = {
    "reserve": lambda api, item, member, at: api.reserve(item, member, at=at),
    "check_out": lambda api, item, member, at: api.post(f"/items/{item}/check-out", at=at),
    "return": lambda api, item, member, at: api.post(f"/items/{item}/return", at=at),
    "cancel_reservation": lambda api, item, member, at: api.delete(
        f"/items/{item}/reservation", at=at
    ),
    "start_maintenance": lambda api, item, member, at: api.post(
        f"/items/{item}/maintenance", at=at
    ),
    "finish_maintenance": lambda api, item, member, at: api.delete(
        f"/items/{item}/maintenance", at=at
    ),
}


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("state", STATES)
def test_a_listed_action_succeeds_and_an_unlisted_one_is_refused(api, state, action):
    arrange, at = STATES[state]
    member, item = api.make_member(), api.make_item()
    arrange(api, item["id"], member["id"])
    offered = actions(api, item["id"], at=at)

    response = ACTIONS[action](api, item["id"], member["id"], at)

    if action in offered:
        assert response.status_code in (200, 201), (state, offered, response.text)
    else:
        assert response.status_code == 409, (state, offered, response.text)
        assert actions(api, item["id"], at=at) == offered  # a refused action changes nothing


def test_every_state_offers_something_so_the_matrix_above_is_not_vacuous(api):
    offered_somewhere = set()
    for state, (arrange, at) in STATES.items():
        member, item = api.make_member(), api.make_item()
        arrange(api, item["id"], member["id"])
        offered = actions(api, item["id"], at=at)
        assert offered, state
        offered_somewhere.update(offered)
    assert offered_somewhere == set(ACTIONS)  # each action is listed (and so exercised) somewhere
