def test_create_user(client):
    response = client.post("/users/", json={"email": "new@example.com", "password": "pw"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert {"id", "created_at"} <= body.keys()
    assert "password" not in body


def test_create_user_duplicate_email_returns_409(client, user):
    response = client.post("/users/", json={"email": user["email"], "password": "other"})

    assert response.status_code == 409


def test_create_user_invalid_email(client):
    response = client.post("/users/", json={"email": "not-an-email", "password": "pw"})

    assert response.status_code == 422


def test_create_user_password_over_72_bytes_is_rejected(client):
    response = client.post("/users/", json={"email": "long@example.com", "password": "x" * 73})

    assert response.status_code == 422


def test_get_user(client, user):
    response = client.get(f"/users/{user['id']}")

    assert response.status_code == 200
    assert response.json()["email"] == user["email"]


def test_get_missing_user_returns_404(client):
    assert client.get("/users/999999").status_code == 404


def test_get_me(client, user, auth_headers):
    response = client.get("/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


def test_get_me_requires_auth(client):
    assert client.get("/users/me").status_code == 401


def test_profile_stats(client, user, auth_headers, other_auth_headers, posts):
    # alice tem 2 posts; bob vota nos dois e alice vota em um dela mesma
    for post in posts[:2]:
        client.post("/vote/", json={"post_id": post["id"], "dir": 1}, headers=other_auth_headers)
    client.post("/vote/", json={"post_id": posts[0]["id"], "dir": 1}, headers=auth_headers)
    client.post(f"/posts/{posts[2]['id']}/comments", json={"content": "oi"}, headers=auth_headers)

    response = client.get(f"/users/{user['id']}/profile", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "alice@example.com"
    assert (body["posts"], body["votes_received"], body["comments"]) == (2, 3, 1)


def test_profile_of_missing_user_returns_404(client, auth_headers):
    assert client.get("/users/999999/profile", headers=auth_headers).status_code == 404


def test_list_posts_filtered_by_owner(client, other_user, auth_headers, posts):
    response = client.get("/posts/", params={"owner_id": other_user["id"]}, headers=auth_headers)

    assert [item["Post"]["id"] for item in response.json()] == [posts[2]["id"]]
