from datetime import datetime
from typing import Annotated

from pydantic import Field

from app.domain.enums import LoanStatus
from app.domain.rules import reservation_expires_at
from app.models import Loan
from app.schemas.common import RequestModel, ResponseModel
from app.services.views import OverdueLoan


class ReserveRequest(RequestModel):
    member_id: Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]


class LoanRead(ResponseModel):
    """A loan as stored. All timestamps are UTC (the UI shows them in IST)."""

    id: int
    member_id: int
    item_id: int
    status: LoanStatus
    reserved_at: datetime
    expires_at: datetime | None = Field(
        description="When the 48-hour hold ends; only set while the loan is reserved"
    )
    checked_out_at: datetime | None
    due_at: datetime | None
    returned_at: datetime | None
    cancelled_at: datetime | None
    fee_charged_paise: int = Field(description="Late fee charged at return; 0 until then")

    @classmethod
    def from_loan(cls, loan: Loan) -> "LoanRead":
        reserved = loan.status is LoanStatus.RESERVED
        return cls(
            id=loan.id,
            member_id=loan.member_id,
            item_id=loan.item_id,
            status=loan.status,
            reserved_at=loan.reserved_at,
            expires_at=reservation_expires_at(loan.reserved_at) if reserved else None,
            checked_out_at=loan.checked_out_at,
            due_at=loan.due_at,
            returned_at=loan.returned_at,
            cancelled_at=loan.cancelled_at,
            fee_charged_paise=loan.fee_charged_paise,
        )


class OverdueLoanRead(ResponseModel):
    loan_id: int
    member_id: int
    member_name: str
    member_phone: str
    item_id: int
    item_name: str
    checked_out_at: datetime
    due_at: datetime
    days_overdue: int = Field(description="Late days so far, rounded up")
    fee_if_returned_now_paise: int = Field(description="What returning it right now would cost")

    @classmethod
    def from_view(cls, view: OverdueLoan) -> "OverdueLoanRead":
        return cls(
            loan_id=view.loan.id,
            member_id=view.loan.member_id,
            member_name=view.member_name,
            member_phone=view.member_phone,
            item_id=view.loan.item_id,
            item_name=view.item_name,
            checked_out_at=view.loan.checked_out_at,
            due_at=view.loan.due_at,
            days_overdue=view.days_overdue,
            fee_if_returned_now_paise=view.fee_if_returned_now_paise,
        )
