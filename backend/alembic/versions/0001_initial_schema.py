"""Initial schema: members, suspensions, items, loans, payments.

This file is a frozen snapshot: it does not import from app.models, so later model changes
cannot silently rewrite history. tests/db/test_migrations.py checks that it still matches the
models (tables, columns, indexes) and tests/db/test_schema.py exercises its constraints.

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ACTIVE = "status IN ('reserved', 'checked_out')"


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("join_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_members_name_not_blank")),
        sa.CheckConstraint(
            "status IN ('active', 'suspended')", name=op.f("ck_members_status_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
    )

    op.create_table(
        "member_suspensions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "lifted_at IS NULL OR lifted_at >= suspended_at",
            name=op.f("ck_member_suspensions_lifted_after_suspended"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_member_suspensions_member_id_members"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_member_suspensions")),
    )
    op.create_index(
        "uq_member_suspensions_one_open",
        "member_suspensions",
        ["member_id"],
        unique=True,
        postgresql_where=sa.text("lifted_at IS NULL"),
        sqlite_where=sa.text("lifted_at IS NULL"),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("replacement_value_paise", sa.Integer(), nullable=False),
        sa.Column("condition_note", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="available", nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_items_name_not_blank")),
        sa.CheckConstraint(
            "replacement_value_paise > 0", name=op.f("ck_items_replacement_value_positive")
        ),
        sa.CheckConstraint(
            "status IN ('available', 'reserved', 'checked_out', 'under_maintenance')",
            name=op.f("ck_items_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items")),
    )
    op.create_index("ix_items_status", "items", ["status"])
    op.create_index("ix_items_category", "items", ["category"])

    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fee_charged_paise", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "status IN ('reserved', 'checked_out', 'returned', 'cancelled', 'expired')",
            name=op.f("ck_loans_status_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'reserved' AND checked_out_at IS NULL AND due_at IS NULL"
            " AND returned_at IS NULL AND cancelled_at IS NULL)"
            " OR (status = 'checked_out' AND checked_out_at IS NOT NULL AND due_at IS NOT NULL"
            " AND returned_at IS NULL AND cancelled_at IS NULL)"
            " OR (status = 'returned' AND checked_out_at IS NOT NULL AND due_at IS NOT NULL"
            " AND returned_at IS NOT NULL AND cancelled_at IS NULL)"
            " OR (status = 'cancelled' AND checked_out_at IS NULL AND due_at IS NULL"
            " AND returned_at IS NULL AND cancelled_at IS NOT NULL)"
            " OR (status = 'expired' AND checked_out_at IS NULL AND due_at IS NULL"
            " AND returned_at IS NULL AND cancelled_at IS NULL)",
            name=op.f("ck_loans_status_matches_timestamps"),
        ),
        sa.CheckConstraint(
            "due_at IS NULL OR due_at > checked_out_at", name=op.f("ck_loans_due_after_checkout")
        ),
        sa.CheckConstraint(
            "returned_at IS NULL OR returned_at >= checked_out_at",
            name=op.f("ck_loans_return_after_checkout"),
        ),
        sa.CheckConstraint(
            "checked_out_at IS NULL OR checked_out_at >= reserved_at",
            name=op.f("ck_loans_checkout_after_reservation"),
        ),
        sa.CheckConstraint("fee_charged_paise >= 0", name=op.f("ck_loans_fee_not_negative")),
        sa.CheckConstraint(
            "fee_charged_paise = 0 OR status = 'returned'",
            name=op.f("ck_loans_fee_only_when_returned"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_loans_member_id_members"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], name=op.f("fk_loans_item_id_items"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loans")),
    )
    op.create_index(
        "uq_loans_one_active_per_item",
        "loans",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE),
        sqlite_where=sa.text(ACTIVE),
    )
    op.create_index("ix_loans_member_status", "loans", ["member_id", "status"])
    op.create_index("ix_loans_item_id", "loans", ["item_id"])
    op.create_index(
        "ix_loans_checked_out_due_at",
        "loans",
        ["due_at"],
        postgresql_where=sa.text("status = 'checked_out'"),
        sqlite_where=sa.text("status = 'checked_out'"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name=op.f("ck_payments_amount_positive")),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_payments_member_id_members"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )
    op.create_index("ix_payments_member_paid_at", "payments", ["member_id", "paid_at"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("loans")
    op.drop_table("items")
    op.drop_table("member_suspensions")
    op.drop_table("members")
