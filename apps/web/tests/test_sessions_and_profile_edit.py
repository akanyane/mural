from urllib.parse import parse_qs

import pytest
from web_helpers import BOB, HTMX, ME, make_post

from posts_web.filters import device_name

CHROME_WIN = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)


def _session(sid, *, current=False, ua=CHROME_WIN, ip="203.0.113.7"):
    return {
        "id": sid,
        "created_at": "2026-11-01T10:00:00Z",
        "last_used_at": "2026-11-15T10:00:00Z",
        "expires_at": "2026-12-15T10:00:00Z",
        "user_agent": ua,
        "ip_address": ip,
        "current": current,
    }


# --- login / logout ----------------------------------------------------------------


def test_login_forwards_browser_and_ip_and_sets_persistent_cookie(client, api):
    api.on("POST", "/login", json={"access_token": "opaque", "token_type": "bearer"})

    response = client.post(
        "/login",
        data={"login": "alice", "password": "pw"},
        headers={"User-Agent": CHROME_WIN, "X-Forwarded-For": "198.51.100.4"},
    )

    sent = api.last("POST", "/login")
    assert sent.headers["User-Agent"] == CHROME_WIN
    assert sent.headers["X-Forwarded-For"] == "198.51.100.4"
    assert parse_qs(sent.content.decode())["username"] == ["alice"]
    cookie = response.headers["set-cookie"]
    assert "access_token=opaque" in cookie and "Max-Age=7776000" in cookie  # 90 dias


def test_logout_revokes_session_on_the_api(logged_client, api):
    api.on("POST", "/logout", status=204)

    response = logged_client.post("/logout")

    assert api.last("POST", "/logout").headers["Authorization"] == "Bearer token-da-alice"
    assert response.headers["location"] == "/login"
    assert 'access_token=""' in response.headers["set-cookie"]


def test_logout_still_clears_cookie_if_session_already_gone(logged_client, api):
    api.on("POST", "/logout", status=401, json={"detail": "Could not validate credentials"})

    response = logged_client.post("/logout")

    assert response.status_code == 303
    assert 'access_token=""' in response.headers["set-cookie"]


# --- sessões ---------------------------------------------------------------------------


def test_sessions_page_lists_devices(logged_client, api):
    api.on(
        "GET",
        "/sessions/",
        json=[_session(1, current=True), _session(2, ua=SAFARI_IPHONE, ip=None)],
    )

    response = logged_client.get("/sessoes")

    assert response.status_code == 200
    html = response.text
    assert "Chrome · Windows" in html and "Safari · iPhone" in html
    assert "este dispositivo" in html
    assert 'hx-delete="/sessoes/2"' in html and 'hx-delete="/sessoes/1"' not in html
    assert "203.0.113.7" in html
    assert "Sair de todas as outras sessões" in html


def test_sessions_page_without_other_sessions_hides_bulk_button(logged_client, api):
    api.on("GET", "/sessions/", json=[_session(1, current=True)])

    assert "Sair de todas as outras sessões" not in logged_client.get("/sessoes").text


def test_revoke_one_session(logged_client, api):
    api.on("DELETE", "/sessions/2", status=204)

    response = logged_client.delete("/sessoes/2", headers=HTMX)

    assert response.status_code == 200 and response.text == ""
    assert api.last("DELETE", "/sessions/2")


def test_revoke_other_sessions_redirects_with_count(logged_client, api):
    api.on("DELETE", "/sessions/others", json={"revoked": 3})
    api.on("GET", "/sessions/", json=[_session(1, current=True)])

    response = logged_client.post("/sessoes/encerrar-outras")
    assert response.headers["location"] == "/sessoes?revoked=3"

    assert "3 sessões encerradas." in logged_client.get("/sessoes?revoked=3").text


def test_sessions_page_requires_login(client):
    assert client.get("/sessoes").headers["location"] == "/login"


@pytest.mark.parametrize(
    ("ua", "expected"),
    [
        (CHROME_WIN, "Chrome · Windows"),
        (SAFARI_IPHONE, "Safari · iPhone"),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Firefox · Linux",
        ),
        ("Mozilla/5.0 (Windows NT 10.0) AppleWebKit Chrome/140 Safari Edg/140", "Edge · Windows"),
        ("python-httpx/0.28", "python-httpx"),
        (None, "Dispositivo desconhecido"),
    ],
)
def test_device_name(ua, expected):
    assert device_name(ua) == expected


# --- perfil: nome de exibição, bio e edição ---------------------------------------------


def test_display_name_and_bio_on_profile_and_cards(logged_client, api):
    bob = {**BOB, "display_name": "Bob Souza", "bio": "Fotógrafo."}
    api.on(
        "GET",
        "/users/bob/profile",
        json={"user": bob, "posts": 1, "votes_received": 0, "comments": 0},
    )
    api.on("GET", "/posts/", json=[make_post(1, owner=bob)])

    html = logged_client.get("/u/bob").text

    assert "<h1>Bob Souza" in html and "@bob" in html
    assert '<p class="profile-bio">Fotógrafo.</p>' in html
    assert 'class="post-author">Bob Souza</a>' in html


def test_own_profile_shows_edit_and_sessions_links(logged_client, api):
    api.on(
        "GET",
        "/users/alice/profile",
        json={"user": ME, "posts": 0, "votes_received": 0, "comments": 0},
    )
    api.on("GET", "/posts/", json=[])

    html = logged_client.get("/u/alice").text

    assert 'href="/perfil/editar"' in html and 'href="/sessoes"' in html
    assert "alice@example.com" in html  # o email vem de /users/me, não do perfil público


def test_edit_profile_page_prefills_fields(logged_client, api):
    api.on("GET", "/users/me", json={**ME, "display_name": "Alice", "bio": "Oi"})

    html = logged_client.get("/perfil/editar").text

    assert 'value="Alice"' in html and 'value="alice"' in html and ">Oi</textarea>" in html
    assert """hx-vals='{"current": "alice"}'""" in html


def test_edit_profile_submits_and_redirects_to_new_username(logged_client, api):
    api.on("PATCH", "/users/me/profile", json={**ME, "username": "alice.s", "display_name": "A"})

    response = logged_client.post(
        "/perfil/editar", data={"username": "Alice.S", "display_name": " A ", "bio": ""}
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/u/alice.s"
    assert api.last_json("PATCH", "/users/me/profile") == {
        "username": "alice.s",
        "display_name": "A",
        "bio": "",
    }


def test_edit_profile_taken_username(logged_client, api):
    api.on(
        "PATCH", "/users/me/profile", status=409, json={"detail": "Username bob is already taken"}
    )

    response = logged_client.post("/perfil/editar", data={"username": "bob"})

    assert response.status_code == 409
    assert "Esse nome de usuário já está em uso." in response.text
    assert 'value="bob"' in response.text


def test_edit_profile_invalid_username_never_reaches_api(logged_client, api):
    response = logged_client.post("/perfil/editar", data={"username": ".alice"})

    assert response.status_code == 422
    assert not any(r.method == "PATCH" for r in api.requests)


def test_check_username_ignores_own_current_name(client, api):
    response = client.get(
        "/register/check-username", params={"username": "Alice", "current": "alice"}
    )

    assert response.text == ""
    assert api.requests == []
