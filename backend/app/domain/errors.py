"""Domain errors. Each rule violation has its own type so the API can map it to a clear response."""

from collections.abc import Sequence

from app.domain.enums import BlockReason


class DomainError(Exception):
    """Base class for business-rule violations (as opposed to bad input or system failures)."""


class EntityNotFound(DomainError):
    """The member, item or loan the request refers to does not exist."""


class InvalidTransition(DomainError):
    """The requested action is not allowed from the current item or loan state."""


class ReservationExpired(InvalidTransition):
    """The 48-hour hold ran out before the reservation was checked out or cancelled."""


class DeletionBlocked(DomainError):
    """A member or item that has loans, payments or suspensions cannot be deleted."""


class ConflictError(DomainError):
    """A concurrent request changed the same record first; the caller may retry."""


class MemberBlocked(DomainError):
    """The member may not reserve or check out; `reasons` says why."""

    def __init__(self, reasons: Sequence[BlockReason]):
        self.reasons = tuple(reasons)
        super().__init__("Member is blocked: " + ", ".join(r.value for r in self.reasons))


class LoanLimitExceeded(DomainError):
    """The member already holds the maximum number of active loans."""


class InvalidPaymentAmount(DomainError):
    """Payment amount must be a positive number of paise."""


class PaymentExceedsBalance(DomainError):
    """Payment is larger than the member's outstanding balance."""
