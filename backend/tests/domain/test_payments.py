import pytest

from app.domain.errors import InvalidPaymentAmount, PaymentExceedsBalance
from app.domain.rules import validate_payment


def test_payment_equal_to_balance_is_accepted():
    validate_payment(amount_paise=12_000, balance_paise=12_000)


def test_partial_payment_is_accepted():
    validate_payment(amount_paise=1, balance_paise=12_000)


def test_payment_one_paisa_over_balance_is_rejected():
    with pytest.raises(PaymentExceedsBalance):
        validate_payment(amount_paise=12_001, balance_paise=12_000)


def test_any_payment_is_rejected_when_nothing_is_owed():
    with pytest.raises(PaymentExceedsBalance):
        validate_payment(amount_paise=1, balance_paise=0)


@pytest.mark.parametrize("amount_paise", [0, -1, -10_000])
def test_payment_must_be_positive(amount_paise):
    with pytest.raises(InvalidPaymentAmount):
        validate_payment(amount_paise=amount_paise, balance_paise=12_000)
