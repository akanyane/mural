import httpx2
import pytest
from fastapi.testclient import TestClient
from web_helpers import ME, FakeApi

from posts_web.main import app, get_http


@pytest.fixture
def api():
    return FakeApi()


@pytest.fixture
def client(api):
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(api.handler), base_url="http://api")
    app.dependency_overrides[get_http] = lambda: http
    # Sem "with": o lifespan (que criaria o cliente HTTP real) não roda.
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


@pytest.fixture
def logged_client(client, api):
    client.cookies.set("access_token", "token-da-alice")
    api.on("GET", "/users/me", json=ME)
    return client
