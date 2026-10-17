from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.domain.enums import ItemStatus
from app.schemas.common import NoNul, Paise, RequestModel, ResponseModel
from app.schemas.loans import LoanRead
from app.services.views import ItemView

ItemName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100),
    NoNul,
]
Category = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=50),
    NoNul,
]
ConditionNote = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, max_length=1000), NoNul
]


class ItemCreate(RequestModel):
    name: ItemName
    category: Category
    replacement_value_paise: Paise
    condition_note: ConditionNote = ""


class ItemUpdate(RequestModel):
    """Only the fields sent are changed. The status cannot be edited here."""

    name: ItemName | None = None
    category: Category | None = None
    replacement_value_paise: Paise | None = None
    condition_note: ConditionNote | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ItemUpdate":
        if all(getattr(self, field) is None for field in type(self).model_fields):
            raise ValueError("Provide at least one field to change")
        return self


class ItemRead(ResponseModel):
    id: int
    name: str
    category: str
    replacement_value_paise: int
    condition_note: str
    status: ItemStatus = Field(
        description="As of now: a lapsed reservation reads as available, a late loan as overdue"
    )
    current_loan: LoanRead | None = Field(description="The reserved or checked-out loan, if any")

    @classmethod
    def from_view(cls, view: ItemView) -> "ItemRead":
        item = view.item
        return cls(
            id=item.id,
            name=item.name,
            category=item.category,
            replacement_value_paise=item.replacement_value_paise,
            condition_note=item.condition_note,
            status=view.status,
            current_loan=LoanRead.from_loan(view.current_loan) if view.current_loan else None,
        )
