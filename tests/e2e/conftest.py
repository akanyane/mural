"""Testes ponta a ponta: o posts-web conversando com a posts-api de verdade.

Tudo roda em memória: o cliente HTTP do web usa um ASGITransport apontando para
o app da API, que por sua vez usa um SQLite temporário. Sem rede, sem processos.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

import httpx2  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from posts_api.database import Base, create_db_engine, get_db  # noqa: E402
from posts_api.main import app as api_app  # noqa: E402
from posts_web.main import app as web_app  # noqa: E402
from posts_web.main import get_http  # noqa: E402


@pytest.fixture
def web(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'e2e.sqlite'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        with session_factory() as session:
            yield session

    http = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=api_app), base_url="http://api")
    api_app.dependency_overrides[get_db] = override_get_db
    web_app.dependency_overrides[get_http] = lambda: http

    yield lambda: TestClient(web_app, follow_redirects=False)

    api_app.dependency_overrides.clear()
    web_app.dependency_overrides.clear()
    engine.dispose()
