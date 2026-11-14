import os
import shutil
from pathlib import Path

# As settings são lidas no import do app, então os valores de teste vêm antes.
os.environ.update(
    {
        "DATABASE_URL": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key-with-at-least-32-bytes!!",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
    }
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from posts_api.database import create_db_engine, get_db  # noqa: E402
from posts_api.main import app  # noqa: E402

API_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def make_alembic_config():
    def make(connection) -> Config:
        config = Config(str(API_ROOT / "alembic.ini"))
        config.attributes["connection"] = connection
        return config

    return make


@pytest.fixture(scope="session")
def template_db(tmp_path_factory, make_alembic_config) -> Path:
    """Banco criado uma vez pelas migrations (que assim também são testadas)."""
    path = tmp_path_factory.mktemp("db") / "template.sqlite"
    engine = create_db_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        command.upgrade(make_alembic_config(connection), "head")
    engine.dispose()
    return path


@pytest.fixture
def engine(template_db, tmp_path):
    """Cada teste recebe uma cópia própria do banco: isolamento total e barato."""
    path = tmp_path / "test.sqlite"
    shutil.copyfile(template_db, path)
    engine = create_db_engine(f"sqlite:///{path}")
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False)


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory):
    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_user(client, email: str, password: str = "secret123") -> dict:
    response = client.post("/users/", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return {**response.json(), "password": password}


def _login(client, user: dict) -> str:
    response = client.post("/login", data={"username": user["email"], "password": user["password"]})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def user(client):
    return _create_user(client, "alice@example.com")


@pytest.fixture
def other_user(client):
    return _create_user(client, "bob@example.com")


@pytest.fixture
def token(client, user):
    return _login(client, user)


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(client, other_user):
    return {"Authorization": f"Bearer {_login(client, other_user)}"}


@pytest.fixture
def posts(client, auth_headers, other_auth_headers):
    """Três posts, em ordem de criação (a listagem devolve do mais novo ao mais velho)."""
    payloads = [
        ({"title": "first post", "content": "hello"}, auth_headers),
        ({"title": "second post", "content": "world"}, auth_headers),
        ({"title": "100% bob", "content": "from bob"}, other_auth_headers),
    ]
    created = []
    for payload, headers in payloads:
        response = client.post("/posts/", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        created.append(response.json())
    return created
