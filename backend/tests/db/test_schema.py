"""Constraints that must hold in the database itself, whatever the application code does."""

from datetime import UTC, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, StatementError

from app.domain.enums import ItemStatus, LoanStatus, MemberStatus
from app.models import Item, Loan, Member, MemberSuspension
from tests.builders import NOW, add_item, add_loan, add_member, add_payment, loan_fields

IST = timezone(timedelta(hours=5, minutes=30))
ACTIVE_STATUSES = [LoanStatus.RESERVED, LoanStatus.CHECKED_OUT]
INACTIVE_STATUSES = [LoanStatus.RETURNED, LoanStatus.CANCELLED, LoanStatus.EXPIRED]


def assert_flush_rejected(session, *accepted_messages: str):
    """Flushing must fail with an integrity error that names the violated constraint.

    PostgreSQL names every constraint in its error. SQLite names CHECK constraints but reports
    unique and foreign-key violations by column (or generically), so those callers pass the
    SQLite wording as a second accepted message.
    """
    with pytest.raises(IntegrityError) as caught:
        session.flush()
    assert any(message in str(caught.value) for message in accepted_messages), str(caught.value)


# --- members and items ---------------------------------------------------------------------


def test_new_member_defaults_to_active(session):
    member = Member(name="Asha Rao", phone="+91 00000 12345", join_date=NOW.date())
    session.add(member)
    session.flush()
    session.refresh(member)

    assert member.status is MemberStatus.ACTIVE


@pytest.mark.parametrize("name", ["", "   "])
def test_member_name_cannot_be_blank(session, name):
    session.add(Member(name=name, phone="+91 00000 12345", join_date=NOW.date()))

    assert_flush_rejected(session, "ck_members_name_not_blank")


def test_new_item_defaults_to_available(session):
    item = Item(name="Hammer", category="Hand Tools", replacement_value_paise=50_000)
    session.add(item)
    session.flush()
    session.refresh(item)

    assert item.status is ItemStatus.AVAILABLE
    assert item.condition_note == ""


@pytest.mark.parametrize("value", [0, -1])
def test_item_replacement_value_must_be_positive(session, value):
    session.add(Item(name="Hammer", category="Hand Tools", replacement_value_paise=value))

    assert_flush_rejected(session, "ck_items_replacement_value_positive")


def test_overdue_is_derived_so_it_cannot_be_stored_on_an_item(session):
    session.add(
        Item(
            name="Hammer",
            category="Hand Tools",
            replacement_value_paise=50_000,
            status=ItemStatus.OVERDUE,
        )
    )

    assert_flush_rejected(session, "ck_items_status_valid")


def insert_loan_with_raw_status(session, member, item, status: str) -> None:
    """Plain SQL insert, so a status the ORM enum would refuse can reach the database."""
    session.execute(
        sa.text(
            "INSERT INTO loans (member_id, item_id, status, reserved_at, checked_out_at, due_at)"
            " VALUES (:member_id, :item_id, :status, :reserved_at, :checked_out_at, :due_at)"
        ),
        {
            "member_id": member.id,
            "item_id": item.id,
            "status": status,
            "reserved_at": NOW.isoformat(),
            "checked_out_at": (NOW + timedelta(hours=1)).isoformat(),
            "due_at": (NOW + timedelta(days=8)).isoformat(),
        },
    )


def test_overdue_cannot_be_stored_as_a_loan_status(session):
    member = add_member(session)
    control_item, item = add_item(session, name="Control"), add_item(session, name="Subject")

    # Control: the identical statement with a legal status is accepted, so the only thing that
    # can be wrong in the next insert is the status value.
    insert_loan_with_raw_status(session, member, control_item, "checked_out")

    # 'overdue' is rejected by two CHECK constraints: the allowed-values list (status_valid) and
    # the status/timestamp pairing (status_matches_timestamps has no 'overdue' branch). Which one
    # is reported depends on the database (PostgreSQL checks constraints alphabetically, SQLite in
    # declaration order), so the test accepts either rather than depending on evaluation order.
    with pytest.raises(
        IntegrityError, match="ck_loans_status_valid|ck_loans_status_matches_timestamps"
    ):
        insert_loan_with_raw_status(session, member, item, "overdue")


# --- one active loan per item (double reservation / double check-out) -----------------------


@pytest.mark.parametrize("second", ACTIVE_STATUSES)
@pytest.mark.parametrize("first", ACTIVE_STATUSES)
def test_item_cannot_have_two_active_loans(session, first, second):
    ann, bob = add_member(session), add_member(session, name="Bob")
    item = add_item(session)
    add_loan(session, ann, item, first)

    session.add(Loan(member=bob, item=item, **loan_fields(second)))

    assert_flush_rejected(
        session, "uq_loans_one_active_per_item", "UNIQUE constraint failed: loans.item_id"
    )


@pytest.mark.parametrize("old_status", INACTIVE_STATUSES)
def test_finished_loans_do_not_block_a_new_reservation(session, old_status):
    ann, bob = add_member(session), add_member(session, name="Bob")
    item = add_item(session)
    add_loan(session, ann, item, old_status)

    new_loan = add_loan(session, bob, item, LoanStatus.RESERVED)

    assert new_loan.id is not None


def test_one_member_can_hold_different_items(session):
    member = add_member(session)

    add_loan(session, member, add_item(session, name="Drill"))
    add_loan(session, member, add_item(session, name="Saw"))


# --- loan lifecycle consistency -------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "bad_fields"),
    [
        (LoanStatus.CHECKED_OUT, {"due_at": None}),
        (LoanStatus.CHECKED_OUT, {"checked_out_at": None}),
        (LoanStatus.RETURNED, {"returned_at": None}),
        (LoanStatus.CANCELLED, {"cancelled_at": None}),
        (LoanStatus.RESERVED, {"checked_out_at": NOW + timedelta(hours=1)}),
        (LoanStatus.RESERVED, {"cancelled_at": NOW + timedelta(hours=1)}),
        (LoanStatus.EXPIRED, {"returned_at": NOW + timedelta(days=3)}),
        (LoanStatus.CHECKED_OUT, {"returned_at": NOW + timedelta(days=3)}),
    ],
)
def test_loan_timestamps_must_match_its_status(session, status, bad_fields):
    member, item = add_member(session), add_item(session)

    with pytest.raises(IntegrityError, match="ck_loans_status_matches_timestamps"):
        add_loan(session, member, item, status, **bad_fields)


def test_due_date_must_be_after_checkout(session):
    member, item = add_member(session), add_item(session)

    with pytest.raises(IntegrityError, match="ck_loans_due_after_checkout"):
        add_loan(
            session,
            member,
            item,
            LoanStatus.CHECKED_OUT,
            checked_out_at=NOW + timedelta(hours=1),
            due_at=NOW + timedelta(hours=1),
        )


def test_return_cannot_precede_checkout(session):
    member, item = add_member(session), add_item(session)

    with pytest.raises(IntegrityError, match="ck_loans_return_after_checkout"):
        add_loan(session, member, item, LoanStatus.RETURNED, returned_at=NOW)


def test_checkout_cannot_precede_reservation(session):
    member, item = add_member(session), add_item(session)

    with pytest.raises(IntegrityError, match="ck_loans_checkout_after_reservation"):
        add_loan(
            session, member, item, LoanStatus.CHECKED_OUT, checked_out_at=NOW - timedelta(hours=1)
        )


def test_fee_is_only_allowed_on_returned_loans(session):
    member, item = add_member(session), add_item(session)

    with pytest.raises(IntegrityError, match="ck_loans_fee_only_when_returned"):
        add_loan(session, member, item, LoanStatus.CHECKED_OUT, fee_charged_paise=1_000)


def test_fee_cannot_be_negative(session):
    member, item = add_member(session), add_item(session)

    with pytest.raises(IntegrityError, match="ck_loans_fee_not_negative"):
        add_loan(session, member, item, LoanStatus.RETURNED, fee_charged_paise=-1)


def test_fee_defaults_to_zero(session):
    member, item = add_member(session), add_item(session)
    loan = add_loan(session, member, item, LoanStatus.RETURNED)
    session.refresh(loan)

    assert loan.fee_charged_paise == 0


# --- foreign keys ---------------------------------------------------------------------------


def test_loan_needs_an_existing_member(session):
    item = add_item(session)
    session.add(Loan(member_id=999_999, item=item, **loan_fields(LoanStatus.RESERVED)))

    assert_flush_rejected(session, "fk_loans_member_id_members", "FOREIGN KEY constraint failed")


def test_loan_needs_an_existing_item(session):
    member = add_member(session)
    session.add(Loan(member=member, item_id=999_999, **loan_fields(LoanStatus.RESERVED)))

    assert_flush_rejected(session, "fk_loans_item_id_items", "FOREIGN KEY constraint failed")


def test_member_with_history_cannot_be_deleted(session):
    member, item = add_member(session), add_item(session)
    add_loan(session, member, item, LoanStatus.RETURNED)

    with pytest.raises(IntegrityError):
        session.execute(sa.delete(Member).where(Member.id == member.id))


# --- payments -------------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [0, -500])
def test_payment_must_be_positive(session, amount):
    member = add_member(session)

    with pytest.raises(IntegrityError, match="ck_payments_amount_positive"):
        add_payment(session, member, amount_paise=amount)


def test_payment_is_stored_in_integer_paise(session):
    member = add_member(session)
    payment = add_payment(session, member, amount_paise=12_345)
    session.refresh(payment)

    assert payment.amount_paise == 12_345
    assert type(payment.amount_paise) is int


# --- suspension history ---------------------------------------------------------------------


def test_member_can_have_many_past_suspensions_but_only_one_open(session):
    member = add_member(session)
    session.add_all(
        [
            MemberSuspension(
                member=member,
                suspended_at=NOW - timedelta(days=30),
                lifted_at=NOW - timedelta(days=20),
            ),
            MemberSuspension(
                member=member,
                suspended_at=NOW - timedelta(days=10),
                lifted_at=NOW - timedelta(days=5),
            ),
            MemberSuspension(member=member, suspended_at=NOW - timedelta(days=1)),
        ]
    )
    session.flush()

    session.add(MemberSuspension(member=member, suspended_at=NOW))

    assert_flush_rejected(
        session,
        "uq_member_suspensions_one_open",
        "UNIQUE constraint failed: member_suspensions.member_id",
    )


def test_suspension_cannot_be_lifted_before_it_started(session):
    member = add_member(session)
    session.add(
        MemberSuspension(member=member, suspended_at=NOW, lifted_at=NOW - timedelta(days=1))
    )

    assert_flush_rejected(session, "ck_member_suspensions_lifted_after_suspended")


# --- timestamps -----------------------------------------------------------------------------


def test_timestamps_come_back_as_utc_whatever_zone_they_went_in_with(session):
    member, item = add_member(session), add_item(session)
    reserved_at_ist = NOW.astimezone(IST)
    loan = add_loan(session, member, item, reserved_at=reserved_at_ist)

    session.expire(loan)

    assert loan.reserved_at == NOW
    assert loan.reserved_at.tzinfo is UTC


def test_naive_datetimes_are_refused(session):
    member, item = add_member(session), add_item(session)

    with pytest.raises(StatementError, match="Naive datetime"):
        add_loan(session, member, item, reserved_at=NOW.replace(tzinfo=None))
