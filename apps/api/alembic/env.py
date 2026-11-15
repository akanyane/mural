from logging.config import fileConfig

from alembic import context

from posts_api.models import Base

config = context.config

# Os testes passam uma conexão pronta em config.attributes["connection"].
external_connection = config.attributes.get("connection")

if config.config_file_name is not None and external_connection is None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    # render_as_batch: o SQLite não suporta a maioria dos ALTER TABLE, então o
    # Alembic recria a tabela por baixo dos panos ("batch mode").
    context.configure(target_metadata=target_metadata, render_as_batch=True, **kwargs)


def run_migrations_offline() -> None:
    from posts_api.config import settings

    _configure(url=settings.database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection, owns_connection: bool) -> None:
    if connection.dialect.name != "sqlite":
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return

    # No SQLite, o batch mode altera uma tabela recriando-a (cria a nova, copia,
    # DROP na antiga, renomeia). Com as foreign keys ligadas, esse DROP dispara os
    # ON DELETE CASCADE e apaga em cascata as linhas que referenciam a tabela
    # (ex.: alterar "users" apagaria posts, votos e comentários). Por isso as FKs
    # ficam desligadas durante as migrations e a integridade é conferida no fim.
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar():
        # O PRAGMA não tem efeito dentro de uma transação já aberta.
        raise RuntimeError(
            "Não foi possível desligar as foreign keys do SQLite antes das migrations "
            "(há uma transação aberta nesta conexão). Abortado para não apagar dados."
        )
    if owns_connection:
        connection.commit()  # encerra o "autobegin" do SQLAlchemy; o Alembic abre a dele
    try:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Migrations deixaram foreign keys inválidas: {violations}")
    finally:
        # Se a conexão for de quem chamou (ex.: testes) e ainda houver transação aberta,
        # isto não tem efeito; o listener "checkout" do engine religa as FKs no próximo uso.
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        if owns_connection:
            connection.commit()


def run_migrations_online() -> None:
    if external_connection is not None:
        _run_with_connection(external_connection, owns_connection=False)
        return

    from posts_api.database import engine

    with engine.connect() as connection:
        _run_with_connection(connection, owns_connection=True)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
