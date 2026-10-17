import pytest

from app.domain.enums import ItemAction, ItemStatus
from app.domain.rules import allowed_item_actions, next_item_status

A = ItemAction
S = ItemStatus


@pytest.mark.parametrize(
    ("status", "has_open_loan", "expected"),
    [
        (S.AVAILABLE, False, [A.RESERVE, A.START_MAINTENANCE]),
        (S.RESERVED, False, [A.CHECK_OUT, A.CANCEL_RESERVATION, A.START_MAINTENANCE]),
        (S.CHECKED_OUT, True, [A.RETURN, A.START_MAINTENANCE]),
        (S.OVERDUE, True, [A.RETURN, A.START_MAINTENANCE]),
        # In maintenance and nobody has it: it can be released, not "returned".
        (S.UNDER_MAINTENANCE, False, [A.FINISH_MAINTENANCE]),
        # Sent to maintenance while on loan: it can only be returned; release comes after.
        (S.UNDER_MAINTENANCE, True, [A.RETURN]),
    ],
)
def test_each_state_offers_exactly_the_valid_actions(status, has_open_loan, expected):
    assert allowed_item_actions(status, has_open_loan=has_open_loan) == expected


@pytest.mark.parametrize("status", list(S))
@pytest.mark.parametrize("has_open_loan", [True, False])
def test_every_offered_action_is_accepted_by_the_state_machine(status, has_open_loan):
    for action in allowed_item_actions(status, has_open_loan=has_open_loan):
        next_item_status(status, action, has_open_loan=has_open_loan)  # must not raise


def test_expiring_a_reservation_is_automatic_and_never_offered():
    for status in S:
        for has_open_loan in (True, False):
            offered = allowed_item_actions(status, has_open_loan=has_open_loan)
            assert A.EXPIRE_RESERVATION not in offered
