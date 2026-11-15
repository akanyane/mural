"""profiles table (split public data from auth users)

Como no Supabase (auth.users x public.profiles): "users" fica só com autenticação
(email, senha) e os dados públicos vão para "profiles", com o mesmo id (1:1).
O username existente é copiado para profiles e removido de users.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("bio", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_profiles_username"),
    )
    op.execute(
        "INSERT INTO profiles (id, username, created_at, updated_at) "
        "SELECT id, username, created_at, created_at FROM users"
    )
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_username", type_="unique")
        batch.drop_column("username")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("username", sa.String(), nullable=True))
    op.execute(
        "UPDATE users SET username = (SELECT username FROM profiles WHERE profiles.id = users.id)"
    )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(), nullable=False)
        batch.create_unique_constraint("uq_users_username", ["username"])
    op.drop_table("profiles")
