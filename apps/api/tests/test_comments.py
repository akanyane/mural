import pytest


def _comment(client, headers, post_id, content="bom post!"):
    return client.post(f"/posts/{post_id}/comments", json={"content": content}, headers=headers)


def test_create_and_list_comments_in_order(client, auth_headers, other_auth_headers, posts):
    post_id = posts[0]["id"]
    first = _comment(client, other_auth_headers, post_id, "  primeiro  ")
    _comment(client, auth_headers, post_id, "segundo")

    assert first.status_code == 201
    body = first.json()
    assert body["content"] == "primeiro"  # espaços nas pontas são removidos
    assert body["owner"]["username"] == "bob"
    assert "email" not in body["owner"]  # autores são públicos, sem email

    listed = client.get(f"/posts/{post_id}/comments", headers=auth_headers).json()
    assert [c["content"] for c in listed] == ["primeiro", "segundo"]


def test_comment_count_appears_on_posts(client, auth_headers, posts):
    post_id = posts[0]["id"]
    _comment(client, auth_headers, post_id)
    _comment(client, auth_headers, post_id)
    client.post("/vote/", json={"post_id": post_id, "dir": 1}, headers=auth_headers)

    post = client.get(f"/posts/{post_id}", headers=auth_headers).json()

    # Contagens independentes: 2 comentários e 1 voto não viram 2 votos.
    assert (post["comments"], post["votes"]) == (2, 1)


@pytest.mark.parametrize("content", ["", "   ", "x" * 1001])
def test_invalid_comment_content_returns_422(client, auth_headers, posts, content):
    assert _comment(client, auth_headers, posts[0]["id"], content).status_code == 422


def test_comment_on_missing_post_returns_404(client, auth_headers):
    assert _comment(client, auth_headers, 999999).status_code == 404
    assert client.get("/posts/999999/comments", headers=auth_headers).status_code == 404


def test_comments_require_auth(client, posts):
    assert client.get(f"/posts/{posts[0]['id']}/comments").status_code == 401
    assert (
        client.post(f"/posts/{posts[0]['id']}/comments", json={"content": "x"}).status_code == 401
    )


def test_author_can_delete_own_comment(client, auth_headers, posts):
    comment = _comment(client, auth_headers, posts[2]["id"]).json()

    assert client.delete(f"/comments/{comment['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/posts/{posts[2]['id']}/comments", headers=auth_headers).json() == []


def test_post_owner_can_delete_comments_on_their_post(
    client, auth_headers, other_auth_headers, posts
):
    comment = _comment(
        client, other_auth_headers, posts[0]["id"]
    ).json()  # bob comenta no post da alice

    assert client.delete(f"/comments/{comment['id']}", headers=auth_headers).status_code == 204


def test_others_cannot_delete_comment(client, auth_headers, other_auth_headers, posts):
    comment = _comment(client, auth_headers, posts[2]["id"]).json()  # alice comenta no post do bob
    stranger = client.post(
        "/users/", json={"email": "carol@example.com", "username": "carol", "password": "pw"}
    )
    assert stranger.status_code == 201
    token = client.post("/login", data={"username": "carol@example.com", "password": "pw"})
    carol = {"Authorization": f"Bearer {token.json()['access_token']}"}

    assert client.delete(f"/comments/{comment['id']}", headers=carol).status_code == 403


def test_delete_missing_comment_returns_404(client, auth_headers):
    assert client.delete("/comments/999999", headers=auth_headers).status_code == 404


def test_deleting_post_deletes_its_comments(client, db_session, auth_headers, posts):
    from posts_api import models

    _comment(client, auth_headers, posts[0]["id"])
    client.delete(f"/posts/{posts[0]['id']}", headers=auth_headers)

    assert db_session.query(models.Comment).count() == 0
