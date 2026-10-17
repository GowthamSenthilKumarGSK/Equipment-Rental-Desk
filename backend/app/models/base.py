from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase

# Stable constraint names make migrations readable and let the tests name what they violate.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""

    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


def enum_column(enum_class: type[StrEnum]) -> sa.Enum:
    """A VARCHAR column that maps to a Python enum (the CHECK constraint is declared separately)."""
    return sa.Enum(
        enum_class,
        native_enum=False,
        create_constraint=False,
        length=20,
        values_callable=lambda e: [member.value for member in e],
    )


def in_list_sql(column: str, values: tuple[StrEnum, ...]) -> str:
    """`status IN ('a', 'b')` for CHECK constraints and partial indexes."""
    quoted = ", ".join(f"'{value.value}'" for value in values)
    return f"{column} IN ({quoted})"
