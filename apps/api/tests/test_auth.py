from datetime import UTC, datetime, timedelta

import jwt
import pytest

from posts_api import models, utils
from posts_api.config import settings


def test_login_returns_token_for_user(client, user):
    response = client.post("/login", data={"username": user["email"], "password": user["password"]})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    payload = jwt.decode(body["access_token"], settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == str(user["id"])


@pytest.mark.parametrize(
    ("email", "password"),
    [("alice@example.com", "wrong-password"), ("nobody@example.com", "secret123")],
)
def test_login_invalid_credentials(client, user, email, password):
    response = client.post("/login", data={"username": email, "password": password})

    assert response.status_code == 403


def test_protected_route_without_token(client):
    assert client.get("/posts/").status_code == 401


def test_protected_route_with_garbage_token(client):
    response = client.get("/posts/", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_protected_route_with_expired_token(client, user):
    expired = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    response = client.get("/posts/", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_token_of_deleted_user_returns_401(client, db_session, user, auth_headers):
    db_session.delete(db_session.get(models.User, user["id"]))
    db_session.commit()

    assert client.get("/posts/", headers=auth_headers).status_code == 401


def test_hash_and_verify_password():
    hashed = utils.hash_password("secret")

    assert utils.verify_password("secret", hashed)
    assert not utils.verify_password("wrong", hashed)


def test_hash_generated_by_old_passlib_still_verifies():
    # Gerado com passlib==1.7.4 + bcrypt==3.2.0 (as versões antigas do projeto)
    # para a senha "secret": usuários já cadastrados continuam conseguindo logar.
    legacy_hash = "$2b$12$X7UO85J2Oz0dIrvukxQxsOVQAfbfdnL7ONZhAD11GAILhBz3Xlmre"

    assert utils.verify_password("secret", legacy_hash)
    assert not utils.verify_password("wrong", legacy_hash)


def test_verify_password_over_72_bytes_returns_false():
    assert utils.verify_password("x" * 100, utils.hash_password("x" * 72)) is False
