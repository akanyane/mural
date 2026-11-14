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
