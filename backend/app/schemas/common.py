from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def reject_nul(value: str | None) -> str | None:
    """PostgreSQL text cannot hold the NUL character, so refuse it up front as invalid input
    (a 422) instead of letting the database fail with a 500. SQLite would have accepted it."""
    if value is not None and "\x00" in value:
        raise ValueError("Text must not contain NUL (0x00) characters")
    return value


# Add to any text that is stored in, or searched against, a database column.
NoNul = AfterValidator(reject_nul)

# Money is a whole number of paise. Strict, so 12.5, "1200" and true are refused, not converted.
MAX_PAISE = 100_000_000  # ₹10,00,000, far above any tool, and well inside a 32-bit column
Paise = Annotated[int, Field(strict=True, gt=0, le=MAX_PAISE)]


class RequestModel(BaseModel):
    """Base for request bodies: unknown fields are an error, not silently ignored."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    results: list[T]
    total: int = Field(description="How many items match, across all pages")
    limit: int
    offset: int
