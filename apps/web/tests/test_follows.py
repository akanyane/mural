from web_helpers import BOB, HTMX, ME, make_post


def _profile(user, **extra):
    return {"user": user, "posts": 0, "votes_received": 0, "comments": 0, **extra}


def test_profile_shows_counts_and_follow_button(logged_client, api):
    api.on("GET", "/users/bob/profile", json=_profile(BOB, followers=12, following=1))
    api.on("GET", "/posts/", json=[])

    html = logged_client.get("/u/bob").text

    assert 'href="/u/bob/seguidores"' in html and ">12</strong> seguidores" in html
    assert 'href="/u/bob/seguindo"' in html and ">1</strong> seguindo" in html
    assert 'hx-put="/u/bob/follow"' in html and "+ Seguir" in html


def test_profile_singular_follower_and_follow_back(logged_client, api):
    api.on("GET", "/users/bob/profile", json=_profile(BOB, followers=1, follows_you=True))
    api.on("GET", "/posts/", json=[])

    html = logged_client.get("/u/bob").text

    assert ">1</strong> seguidor<" in html
    assert "segue você" in html
    assert "+ Seguir de volta" in html


def test_profile_when_already_following(logged_client, api):
    api.on("GET", "/users/bob/profile", json=_profile(BOB, followers=3, is_following=True))
    api.on("GET", "/posts/", json=[])

    html = logged_client.get("/u/bob").text

    assert 'hx-delete="/u/bob/follow"' in html
    assert "✓ Seguindo" in html and "Deixar de seguir" in html


def test_my_profile_has_no_follow_button(logged_client, api):
    api.on("GET", "/users/alice/profile", json=_profile(ME, followers=2))
    api.on("GET", "/posts/", json=[])

    html = logged_client.get("/u/alice").text

    assert "/follow" not in html
    assert ">2</strong> seguidores" in html


def test_follow_calls_api_and_returns_updated_block(logged_client, api):
    api.on("PUT", "/users/bob/follow", status=204)
    api.on("GET", "/users/bob/profile", json=_profile(BOB, followers=13, is_following=True))

    response = logged_client.put("/u/bob/follow", headers=HTMX)

    assert response.status_code == 200
    html = response.text
    assert 'id="profile-social"' in html
    assert 'class="count bump">13<' in html
    assert 'hx-delete="/u/bob/follow"' in html and "pop" in html
    assert api.last("PUT", "/users/bob/follow").headers["Authorization"] == "Bearer token-da-alice"


def test_unfollow_calls_api(logged_client, api):
    api.on("DELETE", "/users/bob/follow", status=204)
    api.on("GET", "/users/bob/profile", json=_profile(BOB, followers=12))

    html = logged_client.delete("/u/bob/follow", headers=HTMX).text

    assert 'hx-put="/u/bob/follow"' in html


def test_follow_yourself_error_shows_flash(logged_client, api):
    api.on("PUT", "/users/alice/follow", status=400, json={"detail": "You cannot follow yourself"})

    response = logged_client.put("/u/alice/follow", headers=HTMX)

    assert response.status_code == 400
    assert response.headers["HX-Retarget"] == "#flash"


def test_followers_page_lists_users(logged_client, api):
    api.on("GET", "/users/bob/profile", json=_profile(BOB, followers=2, following=0))
    api.on(
        "GET",
        "/users/bob/followers",
        json=[
            {"id": 1, "username": "alice", "created_at": "2026-01-01T00:00:00Z"},
            {"id": 3, "username": "carol", "created_at": "2026-02-01T00:00:00Z"},
        ],
    )

    response = logged_client.get("/u/bob/seguidores")

    assert response.status_code == 200
    html = response.text
    assert 'href="/u/alice"' in html and 'href="/u/carol"' in html
    assert ">você<" in html  # alice sou eu
    assert 'aria-current="page"' in html and "2 seguidores" in html
    assert "Carregar mais" not in html


def test_following_page_empty_state(logged_client, api):
    api.on("GET", "/users/bob/profile", json=_profile(BOB))
    api.on("GET", "/users/bob/following", json=[])

    html = logged_client.get("/u/bob/seguindo").text

    assert "@bob ainda não segue ninguém." in html


def test_follow_list_load_more_returns_fragment(logged_client, api):
    page = [{"id": i, "username": f"u{i}", "created_at": "2026-01-01T00:00:00Z"} for i in range(30)]
    api.on("GET", "/users/bob/profile", json=_profile(BOB, followers=45))
    api.on("GET", "/users/bob/followers", json=page)

    first = logged_client.get("/u/bob/seguidores").text
    more = logged_client.get("/u/bob/seguidores?skip=30", headers=HTMX).text

    assert 'hx-get="/u/bob/seguidores?skip=30"' in first
    assert "<html" not in more and 'hx-get="/u/bob/seguidores?skip=60"' in more
    assert api.last("GET", "/users/bob/followers").url.params["skip"] == "30"


def test_feed_tabs_and_following_feed(logged_client, api):
    api.on("GET", "/posts/", json=[make_post(i) for i in range(10, 0, -1)])

    default = logged_client.get("/").text
    assert "following" not in str(api.last("GET", "/posts/").url.params)

    following = logged_client.get("/?feed=seguindo").text
    params = api.last("GET", "/posts/").url.params
    assert params["following"] == "true"
    assert 'href="/?feed=seguindo" class="tab is-active" aria-current="page"' in following
    assert 'href="/" class="tab is-active" aria-current="page"' in default
    # busca e "Carregar mais" continuam no feed "Seguindo"
    assert 'name="feed" value="seguindo"' in following
    assert "&feed=seguindo" in following


def test_following_feed_fragment_and_empty_message(logged_client, api):
    api.on("GET", "/posts/", json=[])

    html = logged_client.get("/posts", params={"feed": "seguindo"}, headers=HTMX).text

    assert api.last("GET", "/posts/").url.params["following"] == "true"
    assert "Siga pessoas para ver os posts delas aqui." in html


def test_unknown_feed_value_falls_back_to_default(logged_client, api):
    api.on("GET", "/posts/", json=[])

    logged_client.get("/?feed=qualquer")

    assert "following" not in str(api.last("GET", "/posts/").url.params)
