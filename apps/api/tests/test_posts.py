def test_list_posts_newest_first_with_votes_and_owner(client, auth_headers, posts):
    client.post("/vote/", json={"post_id": posts[0]["id"], "dir": 1}, headers=auth_headers)

    response = client.get("/posts/", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["Post"]["id"] for item in body] == [post["id"] for post in reversed(posts)]
    assert [item["votes"] for item in body] == [0, 0, 1]
    assert [item["voted"] for item in body] == [False, False, True]
    assert body[-1]["Post"]["owner"]["email"] == "alice@example.com"


def test_voted_flag_is_per_user(client, auth_headers, other_auth_headers, posts):
    post_id = posts[0]["id"]
    client.post("/vote/", json={"post_id": post_id, "dir": 1}, headers=auth_headers)

    mine = client.get(f"/posts/{post_id}", headers=auth_headers).json()
    theirs = client.get(f"/posts/{post_id}", headers=other_auth_headers).json()

    assert (mine["votes"], mine["voted"]) == (1, True)
    assert (theirs["votes"], theirs["voted"]) == (1, False)


def test_list_posts_pagination(client, auth_headers, posts):
    response = client.get("/posts/", params={"limit": 1, "skip": 1}, headers=auth_headers)

    assert [item["Post"]["id"] for item in response.json()] == [posts[1]["id"]]


def test_list_posts_rejects_invalid_pagination(client, auth_headers):
    assert client.get("/posts/", params={"skip": -1}, headers=auth_headers).status_code == 422
    assert client.get("/posts/", params={"limit": 0}, headers=auth_headers).status_code == 422


def test_search_treats_like_wildcards_literally(client, auth_headers, posts):
    by_word = client.get("/posts/", params={"search": "post"}, headers=auth_headers).json()
    by_percent = client.get("/posts/", params={"search": "%"}, headers=auth_headers).json()

    assert {item["Post"]["title"] for item in by_word} == {"first post", "second post"}
    assert [item["Post"]["title"] for item in by_percent] == ["100% bob"]


def test_deleting_user_cascades_to_posts(client, db_session, user, posts, other_auth_headers):
    from posts_api import models

    db_session.delete(db_session.get(models.User, user["id"]))
    db_session.commit()

    remaining = client.get("/posts/", headers=other_auth_headers).json()
    assert [item["Post"]["id"] for item in remaining] == [posts[2]["id"]]


def test_get_post(client, auth_headers, posts):
    response = client.get(f"/posts/{posts[0]['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"Post": posts[0], "votes": 0, "voted": False, "comments": 0}


def test_get_missing_post_returns_404(client, auth_headers):
    assert client.get("/posts/999999", headers=auth_headers).status_code == 404


def test_create_post(client, user, auth_headers):
    response = client.post(
        "/posts/", json={"title": "t", "content": "c", "published": False}, headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["owner_id"] == user["id"]
    assert body["published"] is False


def test_create_post_defaults_published_to_true(client, auth_headers):
    response = client.post("/posts/", json={"title": "t", "content": "c"}, headers=auth_headers)

    assert response.json()["published"] is True


def test_create_post_requires_auth(client):
    assert client.post("/posts/", json={"title": "t", "content": "c"}).status_code == 401


def test_update_own_post(client, auth_headers, posts):
    response = client.put(
        f"/posts/{posts[0]['id']}",
        json={"title": "edited", "content": "new", "published": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["title"], body["content"], body["published"]) == (
        posts[0]["id"],
        "edited",
        "new",
        False,
    )


def test_update_someone_elses_post_returns_403(client, auth_headers, posts):
    response = client.put(
        f"/posts/{posts[2]['id']}", json={"title": "x", "content": "y"}, headers=auth_headers
    )

    assert response.status_code == 403


def test_update_missing_post_returns_404(client, auth_headers):
    response = client.put(
        "/posts/999999", json={"title": "x", "content": "y"}, headers=auth_headers
    )

    assert response.status_code == 404


def test_delete_own_post(client, auth_headers, posts):
    response = client.delete(f"/posts/{posts[0]['id']}", headers=auth_headers)

    assert response.status_code == 204
    assert client.get(f"/posts/{posts[0]['id']}", headers=auth_headers).status_code == 404


def test_delete_someone_elses_post_returns_403(client, auth_headers, posts):
    assert client.delete(f"/posts/{posts[2]['id']}", headers=auth_headers).status_code == 403


def test_delete_missing_post_returns_404(client, auth_headers):
    assert client.delete("/posts/999999", headers=auth_headers).status_code == 404
