from datetime import UTC, datetime

import sqlalchemy as sa


class UtcDateTime(sa.types.TypeDecorator):
    """Timezone-aware DateTime that is always UTC in Python and in storage.

    PostgreSQL stores timestamptz and hands back aware values; SQLite has no timezone support and
    hands back naive ones. This type makes both behave the same: naive input is rejected (a naive
    datetime is almost always a bug), aware input is converted to UTC, and output is aware UTC.
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime: timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:  # SQLite
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
