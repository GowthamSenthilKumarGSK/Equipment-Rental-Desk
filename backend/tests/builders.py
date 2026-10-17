"""Small helpers that insert valid rows so each test only spells out what it is about."""

from datetime import UTC, date, datetime, timedelta

from app.domain.enums import ItemStatus, LoanStatus, MemberStatus
from app.models import Item, Loan, Member, Payment

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)


def add_member(session, **overrides) -> Member:
    fields = {
        "name": "Test Member",
        "phone": "+91 00000 99999",
        "join_date": date(2026, 1, 1),
        "status": MemberStatus.ACTIVE,
    }
    member = Member(**{**fields, **overrides})
    session.add(member)
    session.flush()
    return member


def add_item(session, **overrides) -> Item:
    fields = {
        "name": "Test Drill",
        "category": "Power Tools",
        "replacement_value_paise": 650_000,
        "status": ItemStatus.AVAILABLE,
    }
    item = Item(**{**fields, **overrides})
    session.add(item)
    session.flush()
    return item


def loan_fields(status: LoanStatus, reserved_at: datetime = NOW) -> dict:
    """Timestamps that satisfy the status/timestamp CHECK constraint for `status`."""
    fields: dict = {"status": status, "reserved_at": reserved_at}
    if status in (LoanStatus.CHECKED_OUT, LoanStatus.RETURNED):
        fields["checked_out_at"] = reserved_at + timedelta(hours=1)
        fields["due_at"] = reserved_at + timedelta(hours=1, days=7)
    if status is LoanStatus.RETURNED:
        fields["returned_at"] = reserved_at + timedelta(days=3)
    if status is LoanStatus.CANCELLED:
        fields["cancelled_at"] = reserved_at + timedelta(hours=1)
    return fields


def add_loan(session, member, item, status=LoanStatus.RESERVED, **overrides) -> Loan:
    loan = Loan(member=member, item=item, **{**loan_fields(status), **overrides})
    session.add(loan)
    session.flush()
    return loan


def add_payment(session, member, amount_paise=1_000, **overrides) -> Payment:
    fields = {"amount_paise": amount_paise, "paid_at": NOW, "note": "Cash"}
    payment = Payment(member=member, **{**fields, **overrides})
    session.add(payment)
    session.flush()
    return payment
