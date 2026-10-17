"""Member endpoints: catalogue, suspension, payments and the account statement.

Routes only parse the request, call a service and shape the answer. Every rule is in the service
and domain layers.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import MemberId, MemberServiceDep, PageDep
from app.api.errors import ERROR_RESPONSES
from app.domain.enums import MemberStatus
from app.schemas.common import NoNul, Page
from app.schemas.members import (
    MemberCreate,
    MemberDetail,
    MemberRead,
    MemberUpdate,
    PaymentCreate,
    PaymentRead,
    StatementRead,
    SuspendRequest,
)

router = APIRouter(prefix="/members", tags=["members"], responses=ERROR_RESPONSES)


@router.post("", status_code=201, summary="Register a member")
def create_member(body: MemberCreate, service: MemberServiceDep) -> MemberRead:
    member = service.create_member(name=body.name, phone=body.phone, join_date=body.join_date)
    return MemberRead.model_validate(member)


@router.get("", summary="List members, by name")
def list_members(
    service: MemberServiceDep,
    page: PageDep,
    status: MemberStatus | None = None,
    q: Annotated[
        str | None, Query(max_length=100, description="Name or phone contains"), NoNul
    ] = None,
) -> Page[MemberRead]:
    result = service.list_members(status=status, search=q, limit=page.limit, offset=page.offset)
    return Page(
        results=[MemberRead.model_validate(member) for member in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{member_id}", summary="One member, with balance and why they may be blocked")
def get_member(member_id: MemberId, service: MemberServiceDep) -> MemberDetail:
    return MemberDetail.from_view(service.get_member(member_id))


@router.patch("/{member_id}", summary="Change a member's name or phone")
def update_member(member_id: MemberId, body: MemberUpdate, service: MemberServiceDep) -> MemberRead:
    member = service.update_member(member_id=member_id, name=body.name, phone=body.phone)
    return MemberRead.model_validate(member)


@router.delete(
    "/{member_id}",
    status_code=204,
    summary="Delete a member who has no history",
    description="Members with loans, payments or suspensions cannot be deleted (409); suspend "
    "them instead.",
)
def delete_member(member_id: MemberId, service: MemberServiceDep) -> Response:
    service.delete_member(member_id=member_id)
    return Response(status_code=204)


@router.post("/{member_id}/suspension", summary="Suspend a member")
def suspend_member(
    member_id: MemberId, service: MemberServiceDep, body: SuspendRequest | None = None
) -> MemberRead:
    member = service.suspend(member_id=member_id, reason=body.reason if body else None)
    return MemberRead.model_validate(member)


@router.delete("/{member_id}/suspension", summary="Lift a member's suspension")
def reinstate_member(member_id: MemberId, service: MemberServiceDep) -> MemberRead:
    return MemberRead.model_validate(service.reinstate(member_id=member_id))


@router.post(
    "/{member_id}/payments",
    status_code=201,
    summary="Record a payment towards fees",
    description="Rejected with 422 if it is more than the balance. Paying exactly the balance "
    "is fine.",
)
def record_payment(
    member_id: MemberId, body: PaymentCreate, service: MemberServiceDep
) -> PaymentRead:
    payment = service.record_payment(
        member_id=member_id, amount_paise=body.amount_paise, note=body.note
    )
    return PaymentRead.model_validate(payment)


@router.get(
    "/{member_id}/statement",
    summary="Loan history, fees, payments and current balance",
)
def member_statement(member_id: MemberId, service: MemberServiceDep) -> StatementRead:
    return StatementRead.from_statement(service.statement(member_id))
