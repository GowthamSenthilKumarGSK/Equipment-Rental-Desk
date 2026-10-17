from datetime import timedelta

import sqlalchemy as sa

from app.domain.enums import ACTIVE_LOAN_STATUSES, ItemStatus, LoanStatus, MemberStatus
from app.models import Item, Loan, Member, MemberSuspension, Payment
from app.seed import delete_all_rows, is_seeded, seed_database
from tests.builders import NOW
from tests.markers import awaiting_m2


def count(session, model) -> int:
    return session.scalar(sa.select(sa.func.count()).select_from(model))


def balance_paise(session, member: Member) -> int:
    fees = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Loan.fee_charged_paise), 0)).where(
            Loan.member_id == member.id
        )
    )
    paid = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Payment.amount_paise), 0)).where(
            Payment.member_id == member.id
        )
    )
    return fees - paid


def member_named(session, name: str) -> Member:
    return session.scalars(sa.select(Member).where(Member.name == name)).one()


def test_seed_loads_the_sample_library(session):
    assert seed_database(session, NOW) is True

    assert count(session, Member) == 10
    assert count(session, Item) == 13
    assert count(session, Loan) == 15
    assert count(session, Payment) == 2
    assert count(session, MemberSuspension) == 2


def test_seeding_twice_does_not_duplicate_data(session):
    seed_database(session, NOW)

    assert seed_database(session, NOW) is False
    assert count(session, Member) == 10
    assert is_seeded(session)


def test_reset_clears_everything_so_seed_can_run_again(session):
    seed_database(session, NOW)

    delete_all_rows(session)

    assert count(session, Member) == count(session, Item) == count(session, Loan) == 0
    assert seed_database(session, NOW) is True
    assert count(session, Loan) == 15


def test_item_status_agrees_with_the_loans(session):
    seed_database(session, NOW)

    for item in session.scalars(sa.select(Item)):
        active = [loan for loan in item.loans if loan.status in ACTIVE_LOAN_STATUSES]
        assert len(active) <= 1, item.name
        if active:
            expected = (
                ItemStatus.RESERVED
                if active[0].status is LoanStatus.RESERVED
                else ItemStatus.CHECKED_OUT
            )
            assert item.status is expected, item.name
        else:
            assert item.status in (ItemStatus.AVAILABLE, ItemStatus.UNDER_MAINTENANCE), item.name


def test_seed_contains_the_interesting_situations(session):
    seed_database(session, NOW)

    assert balance_paise(session, member_named(session, "Kavita Iyer")) == 12_000  # blocked: > ₹100
    assert balance_paise(session, member_named(session, "Imran Sheikh")) == 10_000  # exactly ₹100
    assert balance_paise(session, member_named(session, "Farah Qureshi")) == 0

    overdue = session.scalars(
        sa.select(Loan).where(Loan.status == LoanStatus.CHECKED_OUT, Loan.due_at < NOW)
    ).all()
    assert sorted(round((NOW - loan.due_at).total_seconds() / 86400) for loan in overdue) == [
        3,
        16,
        16,
    ]

    expiring = session.scalars(
        sa.select(Loan).where(
            Loan.status == LoanStatus.RESERVED, Loan.reserved_at == NOW - timedelta(hours=47)
        )
    ).all()
    assert len(expiring) == 1

    priya = member_named(session, "Priya Nair")
    assert sum(loan.status in ACTIVE_LOAN_STATUSES for loan in priya.loans) == 3


def test_suspended_member_keeps_history_with_one_open_suspension(session):
    seed_database(session, NOW)
    dinesh = member_named(session, "Dinesh Patel")

    assert dinesh.status is MemberStatus.SUSPENDED
    assert len(dinesh.suspensions) == 2
    assert sum(s.lifted_at is None for s in dinesh.suspensions) == 1


def test_seed_phone_numbers_cannot_belong_to_real_people(session):
    seed_database(session, NOW)

    phones = session.scalars(sa.select(Member.phone)).all()
    assert phones and all(phone.startswith("+91 00000 ") for phone in phones)


@awaiting_m2
def test_seeded_fees_match_the_late_fee_rule(session):
    from app.domain.rules import calculate_late_fee_paise

    seed_database(session, NOW)

    returned = session.scalars(sa.select(Loan).where(Loan.status == LoanStatus.RETURNED)).all()
    assert returned
    for loan in returned:
        expected = calculate_late_fee_paise(
            loan.due_at, loan.returned_at, loan.item.replacement_value_paise
        )
        assert loan.fee_charged_paise == expected, loan.id
