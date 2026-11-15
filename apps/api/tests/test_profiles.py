import pytest
from sqlalchemy import inspect

from posts_api import models


def test_auth_and_public_data_live_in_separate_tables(engine):
    columns = {
        t: {c["name"] for c in inspect(engine).get_columns(t)} for t in ("users", "profiles")
    }

    assert columns["users"] == {"id", "email", "password", "created_at"}
    assert {"id", "username", "display_name", "bio", "created_at", "updated_at"} == columns[
        "profiles"
    ]


def test_signup_creates_user_and_profile_with_same_id(client, db_session, user):
    profile = db_session.get(models.Profile, user["id"])

    assert profile is not None and profile.username == "alice"
    assert profile.user.email == "alice@example.com"


def test_me_includes_private_and_profile_fields(client, user, auth_headers):
    body = client.get("/users/me", headers=auth_headers).json()

    assert body["email"] == "alice@example.com"
    assert (body["username"], body["display_name"], body["bio"]) == ("alice", None, None)


def test_update_profile(client, user, auth_headers):
    response = client.patch(
        "/users/me/profile",
        json={"display_name": "  Alice Silva ", "bio": "Gosto de café.", "username": "Alice.S"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["display_name"], body["bio"], body["username"]) == (
        "Alice Silva",
        "Gosto de café.",
        "alice.s",
    )
    public = client.get("/users/alice.s/profile", headers=auth_headers).json()["user"]
    assert public["display_name"] == "Alice Silva" and "email" not in public


def test_partial_update_and_clearing_fields(client, user, auth_headers):
    client.patch("/users/me/profile", json={"display_name": "A", "bio": "B"}, headers=auth_headers)

    body = client.patch("/users/me/profile", json={"bio": ""}, headers=auth_headers).json()

    assert (body["display_name"], body["bio"], body["username"]) == ("A", None, "alice")


def test_username_null_is_ignored(client, user, auth_headers):
    body = client.patch("/users/me/profile", json={"username": None}, headers=auth_headers).json()

    assert body["username"] == "alice"


def test_update_to_taken_username_returns_409(client, user, other_user, auth_headers):
    response = client.patch("/users/me/profile", json={"username": "BOB"}, headers=auth_headers)

    assert response.status_code == 409


def test_keeping_own_username_is_allowed(client, user, auth_headers):
    response = client.patch("/users/me/profile", json={"username": "alice"}, headers=auth_headers)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [{"username": "a..b"}, {"display_name": "x" * 51}, {"bio": "x" * 161}],
)
def test_invalid_profile_updates_return_422(client, user, auth_headers, payload):
    assert client.patch("/users/me/profile", json=payload, headers=auth_headers).status_code == 422


def test_login_by_username_after_rename(client, user, auth_headers):
    client.patch("/users/me/profile", json={"username": "nova"}, headers=auth_headers)

    response = client.post("/login", data={"username": "nova", "password": user["password"]})

    assert response.status_code == 200


def test_deleting_user_deletes_profile(client, db_session, user):
    db_session.delete(db_session.get(models.User, user["id"]))
    db_session.commit()

    assert db_session.get(models.Profile, user["id"]) is None
