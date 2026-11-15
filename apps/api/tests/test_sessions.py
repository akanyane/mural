from datetime import timedelta

from posts_api import models
from posts_api.config import settings
from posts_api.sessions import as_utc, hash_token, utcnow


def _login(client, login="alice", password="secret123", **headers):
    response = client.post(
        "/login", data={"username": login, "password": password}, headers=headers
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _session(db_session, headers) -> models.UserSession:
    token = headers["Authorization"].removeprefix("Bearer ")
    db_session.expire_all()
    return db_session.query(models.UserSession).filter_by(token_hash=hash_token(token)).one()


def test_logout_revokes_the_session_immediately(client, user, auth_headers):
    assert client.get("/users/me", headers=auth_headers).status_code == 200

    assert client.post("/logout", headers=auth_headers).status_code == 204

    assert client.get("/users/me", headers=auth_headers).status_code == 401
    assert client.post("/logout", headers=auth_headers).status_code == 401


def test_each_login_is_an_independent_session(client, user):
    laptop = _login(client)
    phone = _login(client)

    client.post("/logout", headers=laptop)

    assert client.get("/users/me", headers=laptop).status_code == 401
    assert client.get("/users/me", headers=phone).status_code == 200


def test_list_sessions_marks_current_and_records_device(client, user):
    laptop = _login(
        client, **{"User-Agent": "Laptop/1.0", "X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
    )
    _login(client, **{"User-Agent": "Phone/2.0"})

    sessions = client.get("/sessions/", headers=laptop).json()

    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    assert len(current) == 1
    assert current[0]["user_agent"] == "Laptop/1.0"
    assert current[0]["ip_address"] == "203.0.113.7"
    assert all("token" not in key for s in sessions for key in s)


def test_revoke_a_specific_session(client, user):
    laptop = _login(client, **{"User-Agent": "Laptop"})
    phone = _login(client, **{"User-Agent": "Phone"})
    phone_id = next(
        s["id"] for s in client.get("/sessions/", headers=laptop).json() if not s["current"]
    )

    assert client.delete(f"/sessions/{phone_id}", headers=laptop).status_code == 204

    assert client.get("/users/me", headers=phone).status_code == 401
    assert client.get("/users/me", headers=laptop).status_code == 200


def test_revoke_all_other_sessions(client, user):
    current = _login(client)
    others = [_login(client) for _ in range(3)]

    response = client.delete("/sessions/others", headers=current)

    assert response.json() == {"revoked": 3}
    assert all(client.get("/users/me", headers=h).status_code == 401 for h in others)
    assert client.get("/users/me", headers=current).status_code == 200
    assert len(client.get("/sessions/", headers=current).json()) == 1


def test_cannot_see_or_revoke_other_users_sessions(
    client, user, other_user, auth_headers, other_auth_headers
):
    bob_session_id = client.get("/sessions/", headers=other_auth_headers).json()[0]["id"]

    assert all(
        s["id"] != bob_session_id for s in client.get("/sessions/", headers=auth_headers).json()
    )
    assert client.delete(f"/sessions/{bob_session_id}", headers=auth_headers).status_code == 404
    assert client.get("/users/me", headers=other_auth_headers).status_code == 200


def test_revoke_missing_session_returns_404(client, auth_headers):
    assert client.delete("/sessions/999999", headers=auth_headers).status_code == 404


def test_expired_session_is_rejected_and_deleted(client, db_session, user, auth_headers):
    session = _session(db_session, auth_headers)
    session.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert client.get("/users/me", headers=auth_headers).status_code == 401
    assert db_session.query(models.UserSession).count() == 0


def test_sliding_expiration_extends_active_sessions(client, db_session, user, auth_headers):
    session = _session(db_session, auth_headers)
    stale = utcnow() - timedelta(minutes=settings.session_touch_minutes + 1)
    session.last_used_at = stale
    session.expires_at = utcnow() + timedelta(hours=1)  # perto de expirar
    db_session.commit()

    assert client.get("/users/me", headers=auth_headers).status_code == 200

    session = _session(db_session, auth_headers)
    assert as_utc(session.last_used_at) > stale
    remaining = as_utc(session.expires_at) - utcnow()
    assert remaining > timedelta(days=settings.session_idle_days - 1)


def test_recent_use_does_not_write_on_every_request(client, db_session, user, auth_headers):
    before = _session(db_session, auth_headers).last_used_at

    client.get("/users/me", headers=auth_headers)

    assert _session(db_session, auth_headers).last_used_at == before


def test_sessions_never_outlive_the_absolute_max_age(client, db_session, user, auth_headers):
    session = _session(db_session, auth_headers)
    created = utcnow() - timedelta(days=settings.session_max_age_days - 2)
    session.created_at = created
    session.last_used_at = utcnow() - timedelta(hours=1)
    db_session.commit()

    client.get("/users/me", headers=auth_headers)

    session = _session(db_session, auth_headers)
    assert as_utc(session.expires_at) == created + timedelta(days=settings.session_max_age_days)


def test_login_cleans_up_expired_sessions_of_the_user(client, db_session, user, auth_headers):
    session = _session(db_session, auth_headers)
    session.expires_at = utcnow() - timedelta(days=1)
    db_session.commit()

    _login(client)

    assert db_session.query(models.UserSession).count() == 1


def test_deleting_user_deletes_sessions(client, db_session, user, auth_headers):
    db_session.delete(db_session.get(models.User, user["id"]))
    db_session.commit()

    assert db_session.query(models.UserSession).count() == 0
    assert client.get("/users/me", headers=auth_headers).status_code == 401


def test_sessions_require_auth(client):
    assert client.get("/sessions/").status_code == 401
    assert client.delete("/sessions/others").status_code == 401
