"""Item endpoints: catalogue, reservation, check-out, return and maintenance.

Routes only parse the request, call a service and shape the answer. Every rule is in the service
and domain layers.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import ItemId, ItemServiceDep, LoanServiceDep, PageDep
from app.api.errors import ERROR_RESPONSES
from app.domain.enums import ItemStatus
from app.schemas.common import NoNul, Page
from app.schemas.items import ItemCreate, ItemRead, ItemUpdate
from app.schemas.loans import LoanRead, ReserveRequest

router = APIRouter(prefix="/items", tags=["items"], responses=ERROR_RESPONSES)


@router.post("", status_code=201, summary="Add an item (starts available)")
def create_item(body: ItemCreate, service: ItemServiceDep) -> ItemRead:
    view = service.create_item(
        name=body.name,
        category=body.category,
        replacement_value_paise=body.replacement_value_paise,
        condition_note=body.condition_note,
    )
    return ItemRead.from_view(view)


@router.get(
    "",
    summary="List items, by name",
    description="`status` is the status right now: a lapsed reservation counts as available and a "
    "late loan as overdue.",
)
def list_items(
    service: ItemServiceDep,
    page: PageDep,
    status: ItemStatus | None = None,
    category: Annotated[str | None, Query(max_length=50), NoNul] = None,
    q: Annotated[str | None, Query(max_length=100, description="Name contains"), NoNul] = None,
) -> Page[ItemRead]:
    result = service.list_items(
        status=status, category=category, search=q, limit=page.limit, offset=page.offset
    )
    return Page(
        results=[ItemRead.from_view(view) for view in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{item_id}", summary="One item, with its current status and loan")
def get_item(item_id: ItemId, service: ItemServiceDep) -> ItemRead:
    return ItemRead.from_view(service.get_item(item_id))


@router.patch("/{item_id}", summary="Change an item's details (not its status)")
def update_item(item_id: ItemId, body: ItemUpdate, service: ItemServiceDep) -> ItemRead:
    view = service.update_item(
        item_id=item_id,
        name=body.name,
        category=body.category,
        replacement_value_paise=body.replacement_value_paise,
        condition_note=body.condition_note,
    )
    return ItemRead.from_view(view)


@router.delete(
    "/{item_id}",
    status_code=204,
    summary="Delete an item that has no loan history",
    description="Items that have ever been reserved or lent cannot be deleted (409).",
)
def delete_item(item_id: ItemId, service: ItemServiceDep) -> Response:
    service.delete_item(item_id=item_id)
    return Response(status_code=204)


@router.post(
    "/{item_id}/reservation",
    status_code=201,
    summary="Reserve an available item for a member (48-hour hold)",
)
def reserve_item(item_id: ItemId, body: ReserveRequest, service: LoanServiceDep) -> LoanRead:
    return LoanRead.from_loan(service.reserve_item(member_id=body.member_id, item_id=item_id))


@router.delete("/{item_id}/reservation", summary="Cancel the item's reservation")
def cancel_reservation(item_id: ItemId, service: LoanServiceDep) -> LoanRead:
    return LoanRead.from_loan(service.cancel_reservation(item_id=item_id))


@router.post(
    "/{item_id}/check-out",
    summary="Hand over a reserved item (due in 7 days)",
)
def check_out(item_id: ItemId, service: LoanServiceDep) -> LoanRead:
    return LoanRead.from_loan(service.check_out(item_id=item_id))


@router.post(
    "/{item_id}/return",
    summary="Take back a checked-out item",
    description="Charges the late fee, if any, to the member's balance (see `fee_charged_paise`).",
)
def return_item(item_id: ItemId, service: LoanServiceDep) -> LoanRead:
    return LoanRead.from_loan(service.return_item(item_id=item_id))


@router.post(
    "/{item_id}/maintenance",
    summary="Put an item under maintenance (staff)",
    description="Allowed from any state. A reservation is cancelled; a checked-out loan stays "
    "open.",
)
def start_maintenance(item_id: ItemId, items: ItemServiceDep) -> ItemRead:
    items.start_maintenance(item_id=item_id)
    return ItemRead.from_view(items.get_item(item_id))


@router.delete(
    "/{item_id}/maintenance",
    summary="Bring an item back from maintenance (staff)",
    description="Refused while a member still has the item on loan.",
)
def finish_maintenance(item_id: ItemId, items: ItemServiceDep) -> ItemRead:
    items.finish_maintenance(item_id=item_id)
    return ItemRead.from_view(items.get_item(item_id))
