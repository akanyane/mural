from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine, event, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


def create_db_engine(url: str) -> Engine:
    is_sqlite = make_url(url).get_backend_name() == "sqlite"
    # Rotas síncronas do FastAPI rodam num threadpool; o sqlite3 por padrão
    # recusa uma conexão usada por uma thread diferente da que a criou.
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(url, connect_args=connect_args)

    if is_sqlite:
        # Sem isso o SQLite ignora as foreign keys (e o ON DELETE CASCADE).
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = create_db_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]
