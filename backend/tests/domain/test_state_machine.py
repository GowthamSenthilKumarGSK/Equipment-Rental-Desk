import pytest

from app.domain.enums import ItemAction, ItemStatus, LoanAction, LoanStatus
from app.domain.errors import InvalidTransition
from app.domain.rules import next_item_status, next_loan_status
from tests.markers import awaiting_m2

pytestmark = awaiting_m2

A = ItemStatus
ACT = ItemAction

VALID_ITEM_TRANSITIONS = [
    (A.AVAILABLE, ACT.RESERVE, A.RESERVED),
    (A.RESERVED, ACT.CHECK_OUT, A.CHECKED_OUT),
    (A.RESERVED, ACT.CANCEL_RESERVATION, A.AVAILABLE),
    (A.RESERVED, ACT.EXPIRE_RESERVATION, A.AVAILABLE),
    (A.CHECKED_OUT, ACT.RETURN, A.AVAILABLE),
    (A.OVERDUE, ACT.RETURN, A.AVAILABLE),
    # Maintenance can start from any other state, and ends only by staff action (A3).
    (A.AVAILABLE, ACT.START_MAINTENANCE, A.UNDER_MAINTENANCE),
    (A.RESERVED, ACT.START_MAINTENANCE, A.UNDER_MAINTENANCE),
    (A.CHECKED_OUT, ACT.START_MAINTENANCE, A.UNDER_MAINTENANCE),
    (A.OVERDUE, ACT.START_MAINTENANCE, A.UNDER_MAINTENANCE),
    (A.UNDER_MAINTENANCE, ACT.FINISH_MAINTENANCE, A.AVAILABLE),
    # Item went to maintenance while on loan; returning the loan does not make it available.
    (A.UNDER_MAINTENANCE, ACT.RETURN, A.UNDER_MAINTENANCE),
]


@pytest.mark.parametrize(("current", "action", "expected"), VALID_ITEM_TRANSITIONS)
def test_valid_item_transitions(current, action, expected):
    assert next_item_status(current, action) == expected


def test_every_other_item_transition_is_rejected():
    valid = {(current, action) for current, action, _ in VALID_ITEM_TRANSITIONS}
    invalid = [(s, a) for s in ItemStatus for a in ItemAction if (s, a) not in valid]
    assert invalid, "sanity check: the table should not allow everything"

    for current, action in invalid:
        with pytest.raises(InvalidTransition):
            next_item_status(current, action)


@pytest.mark.parametrize(
    ("current", "action"),
    [
        (A.CHECKED_OUT, ACT.CHECK_OUT),  # double check-out
        (A.OVERDUE, ACT.CHECK_OUT),
        (A.AVAILABLE, ACT.CHECK_OUT),  # no walk-up check-out without a reservation: A1
        (A.AVAILABLE, ACT.RETURN),  # returning an item that is not out is an error
        (A.RESERVED, ACT.RETURN),
        (A.CHECKED_OUT, ACT.RESERVE),
        (A.RESERVED, ACT.RESERVE),
        (A.UNDER_MAINTENANCE, ACT.RESERVE),
        (A.UNDER_MAINTENANCE, ACT.START_MAINTENANCE),
        (A.AVAILABLE, ACT.FINISH_MAINTENANCE),
    ],
)
def test_named_invalid_item_transitions(current, action):
    with pytest.raises(InvalidTransition):
        next_item_status(current, action)


def test_maintenance_cannot_end_while_the_item_is_still_on_loan():
    with pytest.raises(InvalidTransition, match="loan"):
        next_item_status(A.UNDER_MAINTENANCE, ACT.FINISH_MAINTENANCE, has_open_loan=True)


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        (LoanStatus.RESERVED, LoanAction.CHECK_OUT, LoanStatus.CHECKED_OUT),
        (LoanStatus.RESERVED, LoanAction.CANCEL, LoanStatus.CANCELLED),
        (LoanStatus.RESERVED, LoanAction.EXPIRE, LoanStatus.EXPIRED),
        (LoanStatus.CHECKED_OUT, LoanAction.RETURN, LoanStatus.RETURNED),
    ],
)
def test_valid_loan_transitions(current, action, expected):
    assert next_loan_status(current, action) == expected


@pytest.mark.parametrize(
    ("current", "action"),
    [
        (LoanStatus.CHECKED_OUT, LoanAction.CHECK_OUT),  # double check-out
        (LoanStatus.RETURNED, LoanAction.RETURN),  # double return
        (LoanStatus.RESERVED, LoanAction.RETURN),  # return before check-out
        (LoanStatus.CHECKED_OUT, LoanAction.CANCEL),  # cannot cancel once collected
        (LoanStatus.CHECKED_OUT, LoanAction.EXPIRE),
        (LoanStatus.CANCELLED, LoanAction.CHECK_OUT),
        (LoanStatus.EXPIRED, LoanAction.CHECK_OUT),  # too late: reservation lapsed
        (LoanStatus.RETURNED, LoanAction.CHECK_OUT),
        (LoanStatus.CANCELLED, LoanAction.CANCEL),
    ],
)
def test_invalid_loan_transitions(current, action):
    with pytest.raises(InvalidTransition):
        next_loan_status(current, action)
