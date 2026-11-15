from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from posts_api.models import Base


def test_migrations_match_models(engine):
    """O schema gerado pelas migrations precisa bater com os models."""
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == []


def test_downgrade_and_upgrade_again(engine, make_alembic_config):
    with engine.begin() as connection:
        config = make_alembic_config(connection)
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}

        command.upgrade(config, "head")
        assert {"users", "posts", "votes"} <= set(inspect(connection).get_table_names())


def test_foreign_keys_are_enforced(engine):
    """No SQLite as FKs só valem com PRAGMA foreign_keys=ON (ver create_db_engine)."""
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_username_migration_backfills_existing_users(engine, make_alembic_config):
    """Usuários criados antes da 0003 ganham um nome válido e único derivado do email."""
    from posts_schemas import username_error

    with engine.begin() as connection:
        config = make_alembic_config(connection)
        command.downgrade(config, "0002")
        connection.execute(
            text(
                "INSERT INTO users (email, password) VALUES "
                "('Ana.Silva@x.com', 'h'), ('ana.silva@y.com', 'h'), ('..12@z.com', 'h'), "
                "('joão+tag@w.com', 'h')"
            )
        )
        command.upgrade(config, "head")
        usernames = connection.execute(text("SELECT username FROM users ORDER BY id")).scalars()
        usernames = list(usernames)

    assert usernames == ["ana.silva", "ana.silva_2", "user12", "jo_o_tag"]
    assert all(username_error(u) is None for u in usernames)


def test_migrations_preserve_posts_votes_and_comments(engine, make_alembic_config):
    """Regressão: no SQLite, alterar "users" (batch mode) recria a tabela; com as
    FKs ligadas o DROP da tabela antiga apagava em cascata posts, votos e comentários."""
    tables = ("users", "posts", "votes", "comments")

    def counts(connection):
        return {t: connection.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tables}

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, username, password) VALUES (1, 'a@x.com', 'a', 'h')"
            )
        )
        connection.execute(
            text("INSERT INTO posts (id, title, content, owner_id) VALUES (1, 't', 'c', 1)")
        )
        connection.execute(text("INSERT INTO votes (user_id, post_id) VALUES (1, 1)"))
        connection.execute(
            text("INSERT INTO comments (content, post_id, owner_id) VALUES ('oi', 1, 1)")
        )
    with engine.connect() as connection:
        before = counts(connection)
    assert before == {"users": 1, "posts": 1, "votes": 1, "comments": 1}

    # 0003 recria "users" nos dois sentidos (drop/add column).
    for target in ("0002", "head"):
        with engine.connect() as connection:
            command.downgrade(make_alembic_config(connection), target) if target != "head" else (
                command.upgrade(make_alembic_config(connection), target)
            )
            connection.commit()
        with engine.connect() as connection:
            assert counts(connection) == before, f"dados perdidos ao migrar para {target}"
            # as FKs voltam a valer depois das migrations
            assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
