"""follows table

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Integer(), nullable=False),
        sa.Column("followed_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("follower_id != followed_id", name="ck_follows_not_self"),
        sa.ForeignKeyConstraint(["followed_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("follower_id", "followed_id"),
    )
    op.create_index(op.f("ix_follows_followed_id"), "follows", ["followed_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_follows_followed_id"), table_name="follows")
    op.drop_table("follows")
