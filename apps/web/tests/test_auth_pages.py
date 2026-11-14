from urllib.parse import parse_qs

from web_helpers import HTMX, ME


def test_feed_without_session_redirects_to_login(client):
    response = client.get("/")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_page_renders(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert '<form method="post" action="/login">' in response.text


def test_login_sets_httponly_cookie_and_redirects(client, api):
    api.on("POST", "/login", json={"access_token": "jwt-123", "token_type": "bearer"})

    response = client.post("/login", data={"email": "alice@example.com", "password": "pw"})

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "access_token=jwt-123" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    # A API recebe o formulário OAuth2 (username = email).
    sent = parse_qs(api.last("POST", "/login").content.decode())
    assert sent == {"username": ["alice@example.com"], "password": ["pw"]}


def test_login_with_wrong_password_shows_error(client, api):
    api.on("POST", "/login", status=403, json={"detail": "Invalid Credentials"})

    response = client.post("/login", data={"email": "alice@example.com", "password": "bad"})

    assert response.status_code == 401
    assert "Email ou senha inválidos." in response.text
    assert 'value="alice@example.com"' in response.text
    assert "set-cookie" not in response.headers


def test_register_creates_user_and_logs_in(client, api):
    api.on("POST", "/users/", status=201, json=ME)
    api.on("POST", "/login", json={"access_token": "jwt-new", "token_type": "bearer"})

    response = client.post("/register", data={"email": "alice@example.com", "password": "pw"})

    assert response.status_code == 303
    assert "access_token=jwt-new" in response.headers["set-cookie"]
    assert api.last_json("POST", "/users/") == {"email": "alice@example.com", "password": "pw"}


def test_register_duplicate_email_shows_api_message(client, api):
    api.on("POST", "/users/", status=409, json={"detail": "User with email x already exists"})

    response = client.post("/register", data={"email": "x@example.com", "password": "pw"})

    assert response.status_code == 409
    assert "already exists" in response.text


def test_logout_clears_cookie(logged_client):
    response = logged_client.post("/logout")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert 'access_token=""' in response.headers["set-cookie"]


def test_expired_session_on_full_page_redirects_to_login(logged_client, api):
    api.on("GET", "/users/me", status=401, json={"detail": "Could not validate credentials"})
    api.on("GET", "/posts/", status=401, json={"detail": "Could not validate credentials"})

    response = logged_client.get("/")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert 'access_token=""' in response.headers["set-cookie"]


def test_expired_session_on_htmx_request_uses_hx_redirect(logged_client, api):
    api.on("POST", "/vote/", status=401, json={"detail": "Could not validate credentials"})

    response = logged_client.post("/posts/1/vote", data={"dir": 1}, headers=HTMX)

    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/login"
