"""Domain vocabulary shared by the rules, the models and (later) the API."""

from enum import StrEnum


class MemberStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ItemStatus(StrEnum):
    """Item states from the assignment.

    OVERDUE is derived (checked out and past due_at) and is never stored: the items table
    has a CHECK constraint that rejects it.
    """

    AVAILABLE = "available"
    RESERVED = "reserved"
    CHECKED_OUT = "checked_out"
    UNDER_MAINTENANCE = "under_maintenance"
    OVERDUE = "overdue"


STORED_ITEM_STATUSES = tuple(s for s in ItemStatus if s is not ItemStatus.OVERDUE)


class LoanStatus(StrEnum):
    """Loan lifecycle. "Overdue" is not a loan status: it is CHECKED_OUT with now > due_at."""

    RESERVED = "reserved"
    CHECKED_OUT = "checked_out"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# Reserved and checked-out loans occupy an item and count towards a member's loan limit.
ACTIVE_LOAN_STATUSES = (LoanStatus.RESERVED, LoanStatus.CHECKED_OUT)


class ItemAction(StrEnum):
    RESERVE = "reserve"
    CHECK_OUT = "check_out"
    RETURN = "return"
    CANCEL_RESERVATION = "cancel_reservation"
    EXPIRE_RESERVATION = "expire_reservation"
    START_MAINTENANCE = "start_maintenance"
    FINISH_MAINTENANCE = "finish_maintenance"


class LoanAction(StrEnum):
    CHECK_OUT = "check_out"
    RETURN = "return"
    CANCEL = "cancel"
    EXPIRE = "expire"


class BlockReason(StrEnum):
    """Why a member cannot reserve or check out (drives the "why can't this member borrow?" UI)."""

    SUSPENDED = "suspended"
    UNPAID_FEES = "unpaid_fees"
    LONG_OVERDUE = "long_overdue"
