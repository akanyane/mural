"""usernames

Adiciona users.username (único, regras do Instagram). Usuários que já existem
recebem um nome gerado a partir do email (ex.: "Ana.Silva@x.com" -> "ana.silva"),
com sufixo numérico em caso de repetição.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14 00:00:00.000000

"""

import re

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

MAX_LENGTH = 30


def _suggest_username(email: str, user_id: int, taken: set[str]) -> str:
    # Lógica copiada (e congelada) aqui de propósito: migrations não devem
    # depender de código da aplicação que pode mudar depois.
    base = re.sub(r"[^a-z0-9._]", "_", email.split("@", 1)[0].lower())
    base = re.sub(r"\.{2,}", ".", base).strip(".")[:MAX_LENGTH].rstrip(".")
    if not base:
        base = f"user{user_id}"
    if base.isdigit():
        base = f"user{base}"[:MAX_LENGTH]
    candidate, n = base, 2
    while candidate in taken:
        suffix = f"_{n}"
        candidate = base[: MAX_LENGTH - len(suffix)] + suffix
        n += 1
    taken.add(candidate)
    return candidate


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("username", sa.String(), nullable=True))

    bind = op.get_bind()
    users = sa.table(
        "users", sa.column("id", sa.Integer), sa.column("email", sa.String), sa.column("username")
    )
    taken: set[str] = set()
    for user_id, email in bind.execute(sa.select(users.c.id, users.c.email).order_by(users.c.id)):
        username = _suggest_username(email, user_id, taken)
        bind.execute(users.update().where(users.c.id == user_id).values(username=username))

    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(), nullable=False)
        batch.create_unique_constraint("uq_users_username", ["username"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_username", type_="unique")
        batch.drop_column("username")
