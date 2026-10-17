"""Business rules as pure functions: no HTTP, no database, no hidden clock.

M1 status: these are signatures with a precise contract in each docstring; the bodies raise
NotImplementedError until M2. The tests in tests/domain are written against these contracts and
are marked as expected failures until then.

Conventions
- Every datetime is timezone-aware UTC. Naive datetimes raise ValueError.
- "now" is always passed in (see app.clock), so tests never wait or patch time.
- Money is integer paise.
"""

from datetime import datetime, timedelta

from app.domain.enums import (
    BlockReason,
    ItemAction,
    ItemStatus,
    LoanAction,
    LoanStatus,
    MemberStatus,
)


def reservation_expires_at(reserved_at: datetime) -> datetime:
    """reserved_at + 48 hours."""
    raise NotImplementedError("M2")


def is_reservation_expired(reserved_at: datetime, now: datetime) -> bool:
    """True once `now >= reserved_at + 48h`.

    The boundary is exclusive: at 47h59m the hold is still valid, at exactly 48h00m00s and
    after it is expired (assumption A2).
    """
    raise NotImplementedError("M2")


def loan_due_at(checked_out_at: datetime) -> datetime:
    """checked_out_at + 7 days."""
    raise NotImplementedError("M2")


def is_overdue(due_at: datetime, now: datetime) -> bool:
    """True only when `now > due_at` (a loan is still on time at exactly due_at)."""
    raise NotImplementedError("M2")


def late_fee_days(due_at: datetime, returned_at: datetime) -> int:
    """Chargeable late days: elapsed time past due_at in 24h units, rounded up.

    0 if returned at or before due_at; one second late is 1 day; 24h exactly is 1 day;
    24h plus one second is 2 days (assumption A5).
    """
    raise NotImplementedError("M2")


def calculate_late_fee_paise(
    due_at: datetime, returned_at: datetime, replacement_value_paise: int
) -> int:
    """min(days * ₹10, ₹200, replacement value), in paise."""
    raise NotImplementedError("M2")


def effective_item_status(
    stored: ItemStatus,
    *,
    now: datetime,
    reserved_at: datetime | None = None,
    due_at: datetime | None = None,
) -> ItemStatus:
    """Status as the world should see it at `now`, without touching the database.

    - RESERVED with an expired hold is shown as AVAILABLE (expiry at read time).
    - CHECKED_OUT past due_at is shown as OVERDUE.
    - Everything else is returned unchanged.
    """
    raise NotImplementedError("M2")


def next_item_status(
    current: ItemStatus, action: ItemAction, *, has_open_loan: bool = False
) -> ItemStatus:
    """Item state machine. `current` is the effective status (OVERDUE allowed).

    Raises InvalidTransition for anything not in the table. Notable cases (A3, A4):
    - RETURN from CHECKED_OUT/OVERDUE gives AVAILABLE; from UNDER_MAINTENANCE the item stays
      UNDER_MAINTENANCE (it was sent to maintenance while on loan).
    - START_MAINTENANCE is allowed from every state except UNDER_MAINTENANCE.
    - FINISH_MAINTENANCE only from UNDER_MAINTENANCE, and not while `has_open_loan`.
    """
    raise NotImplementedError("M2")


def next_loan_status(current: LoanStatus, action: LoanAction) -> LoanStatus:
    """Loan state machine: RESERVED -> CHECKED_OUT | CANCELLED | EXPIRED; CHECKED_OUT -> RETURNED.

    Raises InvalidTransition otherwise (e.g. returning twice, checking out twice).
    """
    raise NotImplementedError("M2")


def member_block_reasons(
    *,
    status: MemberStatus,
    balance_paise: int,
    longest_overdue: timedelta | None,
) -> list[BlockReason]:
    """Every reason the member cannot reserve or check out (empty list = allowed).

    - SUSPENDED: status is suspended.
    - UNPAID_FEES: balance_paise > ₹100 (exactly ₹100 is allowed).
    - LONG_OVERDUE: longest_overdue > 14 days (exactly 14 days is allowed).
    `longest_overdue` is how far past due the member's most overdue loan is (None if none).
    """
    raise NotImplementedError("M2")


def ensure_member_can_transact(
    *,
    status: MemberStatus,
    balance_paise: int,
    longest_overdue: timedelta | None,
) -> None:
    """Raise MemberBlocked(reasons) if member_block_reasons is not empty."""
    raise NotImplementedError("M2")


def ensure_within_loan_limit(active_loan_count: int) -> None:
    """Raise LoanLimitExceeded if the member already has 3 or more active loans.

    Callers must count only RESERVED and CHECKED_OUT loans whose reservation has not expired.
    """
    raise NotImplementedError("M2")


def validate_payment(amount_paise: int, balance_paise: int) -> None:
    """Raise InvalidPaymentAmount if amount <= 0, PaymentExceedsBalance if amount > balance.

    Paying exactly the balance is allowed. Overpayment is rejected, not turned into credit (A7).
    """
    raise NotImplementedError("M2")
