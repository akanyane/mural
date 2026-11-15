import pytest


def _votes_of(client, headers, post_id):
    return client.get(f"/posts/{post_id}", headers=headers).json()["votes"]


def test_vote_on_post(client, auth_headers, posts):
    response = client.post(
        "/vote/", json={"post_id": posts[2]["id"], "dir": 1}, headers=auth_headers
    )

    assert response.status_code == 201
    assert _votes_of(client, auth_headers, posts[2]["id"]) == 1


def test_vote_twice_returns_409(client, auth_headers, posts):
    payload = {"post_id": posts[0]["id"], "dir": 1}
    client.post("/vote/", json=payload, headers=auth_headers)

    assert client.post("/vote/", json=payload, headers=auth_headers).status_code == 409


def test_remove_vote(client, auth_headers, posts):
    post_id = posts[0]["id"]
    client.post("/vote/", json={"post_id": post_id, "dir": 1}, headers=auth_headers)

    response = client.post("/vote/", json={"post_id": post_id, "dir": 0}, headers=auth_headers)

    assert response.status_code == 201
    assert response.json() == {"message": "successfully deleted vote"}
    assert _votes_of(client, auth_headers, post_id) == 0


def test_remove_missing_vote_returns_404(client, auth_headers, posts):
    response = client.post(
        "/vote/", json={"post_id": posts[0]["id"], "dir": 0}, headers=auth_headers
    )

    assert response.status_code == 404


def test_vote_on_missing_post_returns_404(client, auth_headers):
    response = client.post("/vote/", json={"post_id": 999999, "dir": 1}, headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.parametrize("direction", [-1, 2, -5])
def test_invalid_vote_direction_returns_422(client, auth_headers, posts, direction):
    response = client.post(
        "/vote/", json={"post_id": posts[0]["id"], "dir": direction}, headers=auth_headers
    )

    assert response.status_code == 422


def test_votes_from_different_users_are_counted(client, auth_headers, other_auth_headers, posts):
    post_id = posts[0]["id"]
    client.post("/vote/", json={"post_id": post_id, "dir": 1}, headers=auth_headers)
    client.post("/vote/", json={"post_id": post_id, "dir": 1}, headers=other_auth_headers)

    assert _votes_of(client, auth_headers, post_id) == 2


def test_vote_requires_auth(client, posts):
    assert client.post("/vote/", json={"post_id": posts[0]["id"], "dir": 1}).status_code == 401
