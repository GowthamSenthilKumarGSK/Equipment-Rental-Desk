"""Business rules as pure functions: no HTTP, no database, no hidden clock.

Conventions
- Every datetime is timezone-aware (UTC). Naive datetimes raise ValueError.
- "now" is always passed in (see app.clock), so tests never wait or patch time.
- Money is integer paise. Floats are rejected with TypeError, never rounded.
- Rule violations raise the DomainError subclasses in app.domain.errors.
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
from app.domain.errors import (
    InvalidPaymentAmount,
    InvalidTransition,
    LoanLimitExceeded,
    MemberBlocked,
    PaymentExceedsBalance,
)
from app.domain.policy import (
    BLOCKING_BALANCE_PAISE,
    BLOCKING_OVERDUE,
    LATE_FEE_CAP_PAISE,
    LATE_FEE_PER_DAY_PAISE,
    LOAN_PERIOD,
    MAX_ACTIVE_LOANS,
    RESERVATION_HOLD,
)

_ONE_DAY = timedelta(days=1)


def _require_aware(*moments: datetime) -> None:
    for moment in moments:
        if moment.tzinfo is None:
            raise ValueError("datetimes must be timezone-aware (UTC)")


def _require_paise(value: int, name: str) -> None:
    # bool is a subclass of int, and a float amount would be a binary-float money bug.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer number of paise, got {type(value).__name__}")


def _rupees(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    whole, fraction = divmod(abs(paise), 100)
    return f"{sign}₹{whole}.{fraction:02d}"


def _label(value: ItemStatus | ItemAction | LoanStatus | LoanAction) -> str:
    return value.value.replace("_", " ")


# How each item action reads in "Cannot <phrase> an item that is <status>".
_ITEM_ACTION_PHRASES = {
    ItemAction.CANCEL_RESERVATION: "cancel the reservation on",
    ItemAction.EXPIRE_RESERVATION: "expire the reservation on",
    ItemAction.START_MAINTENANCE: "start maintenance on",
    ItemAction.FINISH_MAINTENANCE: "finish maintenance on",
}


def _item_action_phrase(action: ItemAction) -> str:
    return _ITEM_ACTION_PHRASES.get(action, _label(action))


# --- time-based rules -------------------------------------------------------------------------


def reservation_expires_at(reserved_at: datetime) -> datetime:
    """reserved_at + 48 hours."""
    _require_aware(reserved_at)
    return reserved_at + RESERVATION_HOLD


def is_reservation_expired(reserved_at: datetime, now: datetime) -> bool:
    """True once `now >= reserved_at + 48h`.

    The boundary is exclusive: at 47h59m the hold is still valid, at exactly 48h00m00s and
    after it is expired (assumption A2).
    """
    _require_aware(reserved_at, now)
    return now >= reserved_at + RESERVATION_HOLD


def loan_due_at(checked_out_at: datetime) -> datetime:
    """checked_out_at + 7 days."""
    _require_aware(checked_out_at)
    return checked_out_at + LOAN_PERIOD


def is_overdue(due_at: datetime, now: datetime) -> bool:
    """True only when `now > due_at` (a loan is still on time at exactly due_at)."""
    _require_aware(due_at, now)
    return now > due_at


def late_fee_days(due_at: datetime, returned_at: datetime) -> int:
    """Chargeable late days: elapsed time past due_at in 24h units, rounded up.

    0 if returned at or before due_at; one second late is 1 day; 24h exactly is 1 day;
    24h plus one second is 2 days (assumption A5). Time zones play no part: IST midnight
    does not start a new day, only another 24 elapsed hours does.
    """
    _require_aware(due_at, returned_at)
    late_by = returned_at - due_at
    if late_by <= timedelta(0):
        return 0
    return -(-late_by // _ONE_DAY)  # ceiling division with exact integer arithmetic


def calculate_late_fee_paise(
    due_at: datetime, returned_at: datetime, replacement_value_paise: int
) -> int:
    """min(days * ₹10, ₹200, replacement value), in paise."""
    _require_paise(replacement_value_paise, "replacement_value_paise")
    uncapped = late_fee_days(due_at, returned_at) * LATE_FEE_PER_DAY_PAISE
    return min(uncapped, LATE_FEE_CAP_PAISE, replacement_value_paise)


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
    A RESERVED item needs `reserved_at` and a CHECKED_OUT item needs `due_at`; a missing value
    means the item and its loan disagree, which is reported rather than guessed around.
    """
    _require_aware(now)
    if stored is ItemStatus.RESERVED:
        if reserved_at is None:
            raise ValueError("reserved_at is required to judge a RESERVED item")
        return ItemStatus.AVAILABLE if is_reservation_expired(reserved_at, now) else stored
    if stored is ItemStatus.CHECKED_OUT:
        if due_at is None:
            raise ValueError("due_at is required to judge a CHECKED_OUT item")
        return ItemStatus.OVERDUE if is_overdue(due_at, now) else stored
    return stored


def effective_loan_status(
    status: LoanStatus, *, reserved_at: datetime, now: datetime
) -> LoanStatus:
    """A loan's status at `now`: a RESERVED loan whose hold has lapsed reads as EXPIRED.

    Overdue is not a loan status; it is CHECKED_OUT with `is_overdue(due_at, now)`.
    """
    _require_aware(reserved_at, now)
    if status is LoanStatus.RESERVED and is_reservation_expired(reserved_at, now):
        return LoanStatus.EXPIRED
    return status


# --- state machines ---------------------------------------------------------------------------

_ITEM_TRANSITIONS: dict[tuple[ItemStatus, ItemAction], ItemStatus] = {
    (ItemStatus.AVAILABLE, ItemAction.RESERVE): ItemStatus.RESERVED,
    (ItemStatus.RESERVED, ItemAction.CHECK_OUT): ItemStatus.CHECKED_OUT,
    (ItemStatus.RESERVED, ItemAction.CANCEL_RESERVATION): ItemStatus.AVAILABLE,
    (ItemStatus.RESERVED, ItemAction.EXPIRE_RESERVATION): ItemStatus.AVAILABLE,
    (ItemStatus.CHECKED_OUT, ItemAction.RETURN): ItemStatus.AVAILABLE,
    (ItemStatus.OVERDUE, ItemAction.RETURN): ItemStatus.AVAILABLE,
    # Sent to maintenance while on loan: the loan is returned, the item stays in maintenance (A3).
    (ItemStatus.UNDER_MAINTENANCE, ItemAction.RETURN): ItemStatus.UNDER_MAINTENANCE,
    (ItemStatus.AVAILABLE, ItemAction.START_MAINTENANCE): ItemStatus.UNDER_MAINTENANCE,
    (ItemStatus.RESERVED, ItemAction.START_MAINTENANCE): ItemStatus.UNDER_MAINTENANCE,
    (ItemStatus.CHECKED_OUT, ItemAction.START_MAINTENANCE): ItemStatus.UNDER_MAINTENANCE,
    (ItemStatus.OVERDUE, ItemAction.START_MAINTENANCE): ItemStatus.UNDER_MAINTENANCE,
    (ItemStatus.UNDER_MAINTENANCE, ItemAction.FINISH_MAINTENANCE): ItemStatus.AVAILABLE,
}

_LOAN_TRANSITIONS: dict[tuple[LoanStatus, LoanAction], LoanStatus] = {
    (LoanStatus.RESERVED, LoanAction.CHECK_OUT): LoanStatus.CHECKED_OUT,
    (LoanStatus.RESERVED, LoanAction.CANCEL): LoanStatus.CANCELLED,
    (LoanStatus.RESERVED, LoanAction.EXPIRE): LoanStatus.EXPIRED,
    (LoanStatus.CHECKED_OUT, LoanAction.RETURN): LoanStatus.RETURNED,
}


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
    if action is ItemAction.FINISH_MAINTENANCE and has_open_loan:
        raise InvalidTransition(
            "Cannot finish maintenance while the item is still on loan; return it first"
        )
    try:
        return _ITEM_TRANSITIONS[(current, action)]
    except KeyError:
        raise InvalidTransition(
            f"Cannot {_item_action_phrase(action)} an item that is {_label(current)}"
        ) from None


def next_loan_status(current: LoanStatus, action: LoanAction) -> LoanStatus:
    """Loan state machine: RESERVED -> CHECKED_OUT | CANCELLED | EXPIRED; CHECKED_OUT -> RETURNED.

    Raises InvalidTransition otherwise (e.g. returning twice, checking out twice).
    """
    try:
        return _LOAN_TRANSITIONS[(current, action)]
    except KeyError:
        raise InvalidTransition(
            f"Cannot {_label(action)} a loan that is {_label(current)}"
        ) from None


# --- member eligibility -----------------------------------------------------------------------


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
    _require_paise(balance_paise, "balance_paise")
    reasons = []
    if status is MemberStatus.SUSPENDED:
        reasons.append(BlockReason.SUSPENDED)
    if balance_paise > BLOCKING_BALANCE_PAISE:
        reasons.append(BlockReason.UNPAID_FEES)
    if longest_overdue is not None and longest_overdue > BLOCKING_OVERDUE:
        reasons.append(BlockReason.LONG_OVERDUE)
    return reasons


def ensure_member_can_transact(
    *,
    status: MemberStatus,
    balance_paise: int,
    longest_overdue: timedelta | None,
) -> None:
    """Raise MemberBlocked(reasons) if member_block_reasons is not empty."""
    reasons = member_block_reasons(
        status=status, balance_paise=balance_paise, longest_overdue=longest_overdue
    )
    if reasons:
        raise MemberBlocked(reasons)


def ensure_within_loan_limit(active_loan_count: int) -> None:
    """Raise LoanLimitExceeded if the member already has 3 or more active loans.

    Callers must count only RESERVED and CHECKED_OUT loans whose reservation has not expired.
    """
    if active_loan_count >= MAX_ACTIVE_LOANS:
        raise LoanLimitExceeded(
            f"Member already has {active_loan_count} active loans (maximum {MAX_ACTIVE_LOANS})"
        )


# --- payments ---------------------------------------------------------------------------------


def validate_payment(amount_paise: int, balance_paise: int) -> None:
    """Raise InvalidPaymentAmount if amount <= 0, PaymentExceedsBalance if amount > balance.

    Paying exactly the balance is allowed. Overpayment is rejected, not turned into credit (A7).
    """
    _require_paise(amount_paise, "amount_paise")
    _require_paise(balance_paise, "balance_paise")
    if amount_paise <= 0:
        raise InvalidPaymentAmount("Payment amount must be greater than zero")
    if amount_paise > balance_paise:
        raise PaymentExceedsBalance(
            f"Payment of {_rupees(amount_paise)} is more than the outstanding "
            f"balance of {_rupees(balance_paise)}"
        )
