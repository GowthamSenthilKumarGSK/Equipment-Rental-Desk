import pytest

from app.domain.errors import LoanLimitExceeded
from app.domain.rules import ensure_within_loan_limit, has_reached_loan_limit


@pytest.mark.parametrize(
    ("count", "reached"), [(0, False), (1, False), (2, False), (3, True), (4, True)]
)
def test_the_limit_is_reached_at_three_active_loans(count, reached):
    assert has_reached_loan_limit(count) is reached


@pytest.mark.parametrize("count", range(0, 7))
def test_the_flag_and_the_refusal_always_agree(count):
    if has_reached_loan_limit(count):
        with pytest.raises(LoanLimitExceeded):
            ensure_within_loan_limit(count)
    else:
        ensure_within_loan_limit(count)  # must not raise
