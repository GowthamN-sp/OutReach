"""Recoverable campaign deletion and archiving; retain all history."""

import sqlalchemy as sa

from alembic import op

revision = "c93f50b8e721"
down_revision = "b82e49a7d610"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("campaigns", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("campaigns", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_table(
        "inbox_syncs",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("occurred", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("detail", sa.String(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Restore a reviewed backup to preserve campaign recovery data")
