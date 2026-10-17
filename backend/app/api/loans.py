"""Loan reports. Loans are created and changed through the item endpoints."""

from fastapi import APIRouter

from app.api.deps import LoanServiceDep, PageDep
from app.api.errors import ERROR_RESPONSES
from app.schemas.common import Page
from app.schemas.loans import OverdueLoanRead

router = APIRouter(prefix="/loans", tags=["loans"], responses=ERROR_RESPONSES)


@router.get(
    "/overdue",
    summary="Overdue loans, longest overdue first",
    description="Checked-out loans past their due time. Exactly at the due time is still on time.",
)
def overdue_loans(service: LoanServiceDep, page: PageDep) -> Page[OverdueLoanRead]:
    result = service.overdue_loans(limit=page.limit, offset=page.offset)
    return Page(
        results=[OverdueLoanRead.from_view(view) for view in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )
