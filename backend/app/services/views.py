"""Read results returned by the services: ORM rows plus the values worked out for the caller."""

from dataclasses import dataclass
from datetime import timedelta

from app.domain.enums import BlockReason, ItemAction, ItemStatus, LoanStatus
from app.models import Item, Loan, Member, Payment


@dataclass(frozen=True)
class Page[T]:
    """One page of a list, and how many items matched in all."""

    items: list[T]
    total: int


@dataclass(frozen=True)
class ItemView:
    item: Item
    status: ItemStatus  # as of now: a lapsed reservation reads as available, a late loan as overdue
    current_loan: Loan | None  # the reserved or checked-out loan, if any
    allowed_actions: list[ItemAction]  # what staff can do with the item right now


@dataclass(frozen=True)
class MemberView:
    member: Member
    balance_paise: int
    active_loan_count: int
    block_reasons: list[BlockReason]  # empty when the member may reserve and check out
    at_loan_limit: bool  # cannot reserve another item (check-out of a held reservation is fine)


@dataclass(frozen=True)
class StatementLoan:
    loan: Loan
    item_name: str
    status: LoanStatus  # as of now: a lapsed reservation reads as expired
    is_overdue: bool
    days_overdue: int  # late days so far (rounded up); 0 unless overdue


@dataclass(frozen=True)
class Statement:
    member: Member
    balance_paise: int
    total_fees_paise: int
    total_payments_paise: int
    active_loan_count: int
    longest_overdue: timedelta | None
    block_reasons: list[BlockReason]
    at_loan_limit: bool
    loans: list[StatementLoan]
    payments: list[Payment]


@dataclass(frozen=True)
class OverdueLoan:
    loan: Loan
    member_name: str
    member_phone: str
    item_name: str
    days_overdue: int
    fee_if_returned_now_paise: int
