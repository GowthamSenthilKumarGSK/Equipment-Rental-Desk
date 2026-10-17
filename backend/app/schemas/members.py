from datetime import date, datetime
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.domain.enums import BlockReason, LoanStatus, MemberStatus
from app.schemas.common import NoNul, Paise, RequestModel, ResponseModel
from app.schemas.loans import LoanRead
from app.services.views import MemberView, Statement

MemberName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100),
    NoNul,
]
# Digits with an optional leading +, spaces, dashes and brackets; at most 20 characters.
Phone = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()-]{4,19}$"),
    NoNul,
]
Note = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, max_length=200), NoNul]


class MemberCreate(RequestModel):
    name: MemberName
    phone: Phone
    join_date: date | None = Field(default=None, description="Defaults to today (IST)")


class MemberUpdate(RequestModel):
    """Only the fields sent are changed. Use the suspension endpoints to change the status."""

    name: MemberName | None = None
    phone: Phone | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "MemberUpdate":
        if self.name is None and self.phone is None:
            raise ValueError("Provide at least one field to change")
        return self


class SuspendRequest(RequestModel):
    reason: Note | None = None


class PaymentCreate(RequestModel):
    amount_paise: Paise
    note: Note | None = None


class MemberRead(ResponseModel):
    id: int
    name: str
    phone: str
    join_date: date
    status: MemberStatus


class MemberDetail(MemberRead):
    balance_paise: int = Field(description="Fees charged at return minus payments")
    active_loan_count: int = Field(description="Reserved (unexpired), checked out or overdue")
    block_reasons: list[BlockReason] = Field(
        description="Why the member cannot reserve or check out right now; empty if they can"
    )

    @classmethod
    def from_view(cls, view: MemberView) -> "MemberDetail":
        member = view.member
        return cls(
            id=member.id,
            name=member.name,
            phone=member.phone,
            join_date=member.join_date,
            status=member.status,
            balance_paise=view.balance_paise,
            active_loan_count=view.active_loan_count,
            block_reasons=view.block_reasons,
        )


class PaymentRead(ResponseModel):
    id: int
    member_id: int
    amount_paise: int
    paid_at: datetime
    note: str | None


class StatementLoanRead(ResponseModel):
    loan: LoanRead
    item_name: str
    status: LoanStatus = Field(description="As of now: a lapsed reservation reads as expired")
    is_overdue: bool
    days_overdue: int = Field(description="Late days so far, rounded up; 0 unless overdue")


class StatementRead(ResponseModel):
    member: MemberRead
    balance_paise: int
    total_fees_paise: int
    total_payments_paise: int
    active_loan_count: int
    block_reasons: list[BlockReason]
    loans: list[StatementLoanRead] = Field(description="Newest first")
    payments: list[PaymentRead] = Field(description="Newest first")

    @classmethod
    def from_statement(cls, statement: Statement) -> "StatementRead":
        return cls(
            member=MemberRead.model_validate(statement.member),
            balance_paise=statement.balance_paise,
            total_fees_paise=statement.total_fees_paise,
            total_payments_paise=statement.total_payments_paise,
            active_loan_count=statement.active_loan_count,
            block_reasons=statement.block_reasons,
            loans=[
                StatementLoanRead(
                    loan=LoanRead.from_loan(row.loan),
                    item_name=row.item_name,
                    status=row.status,
                    is_overdue=row.is_overdue,
                    days_overdue=row.days_overdue,
                )
                for row in statement.loans
            ],
            payments=[PaymentRead.model_validate(payment) for payment in statement.payments],
        )
