from datetime import timedelta

import pytest

from app.domain.enums import BlockReason, MemberStatus
from app.domain.errors import EntityNotFound, InvalidPaymentAmount, PaymentExceedsBalance
from app.models import Payment
from tests.builders import NOW


def test_balance_is_fees_charged_minus_payments(db, members):
    member_id = db.member()
    db.owing(member_id, 8_000)
    db.owing(member_id, 5_000)
    db.payment(member_id, 1_000)

    assert members.balance_paise(member_id) == 12_000


def test_a_payment_reduces_the_balance_and_is_recorded(db, members, clock):
    member_id = db.member()
    db.owing(member_id, 12_000)
    clock.advance(timedelta(hours=3))

    payment = members.record_payment(member_id=member_id, amount_paise=4_500, note="UPI")

    stored = db.get(Payment, payment.id)
    assert (stored.member_id, stored.amount_paise, stored.note) == (member_id, 4_500, "UPI")
    assert stored.paid_at == NOW + timedelta(hours=3)
    assert members.balance_paise(member_id) == 7_500


def test_a_payment_equal_to_the_balance_clears_it(db, members):
    member_id = db.member()
    db.owing(member_id, 12_000)

    members.record_payment(member_id=member_id, amount_paise=12_000)

    assert members.balance_paise(member_id) == 0


def test_several_payments_can_add_up_to_the_balance(db, members):
    member_id = db.member()
    db.owing(member_id, 10_000)

    for amount in (2_500, 2_500, 5_000):
        members.record_payment(member_id=member_id, amount_paise=amount)

    assert members.balance_paise(member_id) == 0
    with pytest.raises(PaymentExceedsBalance):
        members.record_payment(member_id=member_id, amount_paise=1)


def test_overpayment_is_rejected_and_nothing_is_recorded(db, members):
    member_id = db.member()
    db.owing(member_id, 12_000)

    with pytest.raises(PaymentExceedsBalance, match="₹120.01 is more than .* ₹120.00"):
        members.record_payment(member_id=member_id, amount_paise=12_001)

    assert db.payments_of(member_id) == []
    assert members.balance_paise(member_id) == 12_000


def test_paying_when_nothing_is_owed_is_rejected(db, members):
    member_id = db.member()

    with pytest.raises(PaymentExceedsBalance):
        members.record_payment(member_id=member_id, amount_paise=100)


@pytest.mark.parametrize("amount", [0, -1, -5_000])
def test_payment_must_be_positive(db, members, amount):
    member_id = db.member()
    db.owing(member_id, 12_000)

    with pytest.raises(InvalidPaymentAmount):
        members.record_payment(member_id=member_id, amount_paise=amount)

    assert db.payments_of(member_id) == []


def test_amount_must_be_whole_paise_not_a_float(db, members):
    member_id = db.member()
    db.owing(member_id, 12_000)

    with pytest.raises(TypeError, match="integer"):
        members.record_payment(member_id=member_id, amount_paise=100.5)


def test_unknown_member_is_not_found(members):
    with pytest.raises(EntityNotFound):
        members.record_payment(member_id=999, amount_paise=100)
    with pytest.raises(EntityNotFound):
        members.balance_paise(999)


def test_paying_off_just_enough_unblocks_the_member(db, loans, members):
    """Over ₹100 blocks reserving; paying down to exactly ₹100 lifts the block."""
    member_id, item_id = db.member(), db.item()
    db.owing(member_id, 10_001)
    assert members.block_reasons(member_id) == [BlockReason.UNPAID_FEES]

    members.record_payment(member_id=member_id, amount_paise=1)

    assert members.balance_paise(member_id) == 10_000
    assert members.block_reasons(member_id) == []
    assert loans.reserve_item(member_id=member_id, item_id=item_id).id


def test_a_suspended_member_can_still_pay_their_fees(db, members):
    member_id = db.member(status=MemberStatus.SUSPENDED)
    db.owing(member_id, 3_000)

    members.record_payment(member_id=member_id, amount_paise=3_000)

    assert members.balance_paise(member_id) == 0
