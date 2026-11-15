import pytest


def _profile(client, headers, username):
    return client.get(f"/users/{username}/profile", headers=headers).json()


def test_follow_and_unfollow_update_profile(
    client, user, other_user, auth_headers, other_auth_headers
):
    assert client.put("/users/bob/follow", headers=auth_headers).status_code == 204

    bob_seen_by_alice = _profile(client, auth_headers, "bob")
    assert (bob_seen_by_alice["followers"], bob_seen_by_alice["following"]) == (1, 0)
    assert bob_seen_by_alice["is_following"] is True
    assert bob_seen_by_alice["follows_you"] is False

    alice_seen_by_bob = _profile(client, other_auth_headers, "alice")
    assert (alice_seen_by_bob["followers"], alice_seen_by_bob["following"]) == (0, 1)
    assert alice_seen_by_bob["follows_you"] is True  # "segue você"

    assert client.delete("/users/bob/follow", headers=auth_headers).status_code == 204
    after = _profile(client, auth_headers, "bob")
    assert (after["followers"], after["is_following"]) == (0, False)


def test_follow_and_unfollow_are_idempotent(client, user, other_user, auth_headers):
    for _ in range(2):
        assert client.put("/users/bob/follow", headers=auth_headers).status_code == 204
    assert _profile(client, auth_headers, "bob")["followers"] == 1

    for _ in range(2):
        assert client.delete("/users/bob/follow", headers=auth_headers).status_code == 204
    assert _profile(client, auth_headers, "bob")["followers"] == 0


def test_cannot_follow_yourself(client, user, auth_headers):
    response = client.put("/users/alice/follow", headers=auth_headers)

    assert response.status_code == 400
    assert _profile(client, auth_headers, "alice")["followers"] == 0


def test_follow_unknown_user_returns_404(client, auth_headers):
    assert client.put("/users/ninguem/follow", headers=auth_headers).status_code == 404
    assert client.delete("/users/ninguem/follow", headers=auth_headers).status_code == 404


def test_follow_requires_auth(client, other_user):
    assert client.put("/users/bob/follow").status_code == 401


def test_username_is_case_insensitive(client, other_user, auth_headers):
    assert client.put("/users/BOB/follow", headers=auth_headers).status_code == 204
    assert _profile(client, auth_headers, "bob")["is_following"] is True


def test_followers_and_following_lists_hide_emails(
    client, user, other_user, auth_headers, other_auth_headers
):
    client.post(
        "/users/", json={"email": "carol@example.com", "username": "carol", "password": "pw"}
    )
    carol_token = client.post("/login", data={"username": "carol", "password": "pw"}).json()
    carol = {"Authorization": f"Bearer {carol_token['access_token']}"}

    client.put("/users/bob/follow", headers=auth_headers)  # alice -> bob
    client.put("/users/bob/follow", headers=carol)  # carol -> bob (mais recente)
    client.put("/users/carol/follow", headers=other_auth_headers)  # bob -> carol

    followers = client.get("/users/bob/followers", headers=auth_headers).json()
    following = client.get("/users/bob/following", headers=auth_headers).json()

    assert [u["username"] for u in followers] == ["carol", "alice"]
    assert [u["username"] for u in following] == ["carol"]
    assert all("email" not in u for u in followers + following)


def test_followers_pagination(client, user, other_user, auth_headers):
    client.put("/users/bob/follow", headers=auth_headers)

    page = client.get("/users/bob/followers", params={"limit": 1, "skip": 1}, headers=auth_headers)

    assert page.json() == []
    assert (
        client.get("/users/bob/followers", params={"limit": 0}, headers=auth_headers).status_code
        == 422
    )


def test_following_feed_shows_followed_users_and_my_posts(
    client, auth_headers, other_auth_headers, posts
):
    # posts: 0 e 1 da alice, 2 do bob. Um terceiro usuário também posta.
    client.post(
        "/users/", json={"email": "carol@example.com", "username": "carol", "password": "pw"}
    )
    carol_token = client.post("/login", data={"username": "carol", "password": "pw"}).json()
    carol = {"Authorization": f"Bearer {carol_token['access_token']}"}
    carol_post = client.post(
        "/posts/", json={"title": "da carol", "content": "c"}, headers=carol
    ).json()

    def feed_ids():
        response = client.get("/posts/", params={"following": True}, headers=auth_headers)
        return {item["Post"]["id"] for item in response.json()}

    mine = {posts[0]["id"], posts[1]["id"]}
    assert feed_ids() == mine  # sem seguir ninguém: só os meus

    client.put("/users/carol/follow", headers=auth_headers)
    assert feed_ids() == mine | {carol_post["id"]}  # bob não entra: não sigo o bob

    everything = client.get("/posts/", headers=auth_headers).json()
    assert len(everything) == 4  # o feed padrão continua com todos


def test_deleting_user_removes_their_follows(client, db_session, user, other_user, auth_headers):
    from posts_api import models

    client.put("/users/bob/follow", headers=auth_headers)
    db_session.delete(db_session.get(models.User, other_user["id"]))
    db_session.commit()

    assert db_session.query(models.Follow).count() == 0


@pytest.mark.parametrize("path", ["followers", "following"])
def test_lists_of_unknown_user_return_404(client, auth_headers, path):
    assert client.get(f"/users/ninguem/{path}", headers=auth_headers).status_code == 404
