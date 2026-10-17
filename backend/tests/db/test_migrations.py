import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.models import Base
from tests.conftest import alembic_config

EXPECTED_TABLES = {"members", "member_suspensions", "items", "loans", "payments"}


def test_migration_creates_the_expected_tables(migrated_engine):
    tables = set(sa.inspect(migrated_engine).get_table_names())

    assert tables >= EXPECTED_TABLES


def test_migration_matches_the_models(migrated_engine):
    """Fails if a model changes without a migration (tables, columns, indexes, foreign keys)."""
    with migrated_engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert differences == []


def test_migration_can_be_reversed_and_reapplied(migrated_engine, database_url):
    config = alembic_config(database_url)

    try:
        command.downgrade(config, "base")
        assert not EXPECTED_TABLES & set(sa.inspect(migrated_engine).get_table_names())
    finally:
        command.upgrade(config, "head")

    assert set(sa.inspect(migrated_engine).get_table_names()) >= EXPECTED_TABLES
