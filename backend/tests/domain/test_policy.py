"""The Problem 1 numbers, pinned so a careless edit to policy.py is caught."""

from datetime import timedelta

from app.domain import policy


def test_problem_1_numbers():
    assert timedelta(hours=48) == policy.RESERVATION_HOLD
    assert timedelta(days=7) == policy.LOAN_PERIOD
    assert policy.LATE_FEE_PER_DAY_PAISE == 1_000  # ₹10
    assert policy.LATE_FEE_CAP_PAISE == 20_000  # ₹200
    assert policy.MAX_ACTIVE_LOANS == 3
    assert policy.BLOCKING_BALANCE_PAISE == 10_000  # ₹100
    assert timedelta(days=14) == policy.BLOCKING_OVERDUE


def test_money_constants_are_integers_not_floats():
    for value in (
        policy.LATE_FEE_PER_DAY_PAISE,
        policy.LATE_FEE_CAP_PAISE,
        policy.BLOCKING_BALANCE_PAISE,
    ):
        assert type(value) is int
