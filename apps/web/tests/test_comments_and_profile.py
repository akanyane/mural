from web_helpers import BOB, HTMX, ME, make_comment, make_post


def test_card_has_comment_toggle_with_count_and_profile_links(logged_client, api):
    api.on("GET", "/posts/", json=[make_post(7, owner=BOB, comments=4)])

    html = logged_client.get("/").text

    assert 'hx-get="/posts/7/comments"' in html
    assert 'id="comment-count-7" class="chip-count">4<' in html
    assert 'href="/u/bob"' in html  # autor do post leva ao perfil
    assert 'href="/u/alice"' in html  # "eu" no topo leva ao meu perfil


def test_comments_panel_lists_comments_and_delete_permissions(logged_client, api):
    # post do Bob: posso apagar só o meu comentário (não sou dono do post)
    api.on("GET", "/posts/7", json=make_post(7, owner=BOB))
    api.on(
        "GET",
        "/posts/7/comments",
        json=[make_comment(1, post_id=7, owner=BOB, content="do bob"), make_comment(2, post_id=7)],
    )

    response = logged_client.get("/posts/7/comments", headers=HTMX)

    assert response.status_code == 200
    html = response.text
    assert "do bob" in html and 'id="comment-2"' in html
    assert 'hx-delete="/posts/7/comments/2"' in html
    assert 'hx-delete="/posts/7/comments/1"' not in html
    assert 'hx-post="/posts/7/comments"' in html


def test_post_owner_can_delete_any_comment_on_their_post(logged_client, api):
    api.on("GET", "/posts/1", json=make_post(1))  # post meu
    api.on("GET", "/posts/1/comments", json=[make_comment(1, owner=BOB)])

    html = logged_client.get("/posts/1/comments", headers=HTMX).text

    assert 'hx-delete="/posts/1/comments/1"' in html


def test_empty_comments_panel(logged_client, api):
    api.on("GET", "/posts/1", json=make_post(1))
    api.on("GET", "/posts/1/comments", json=[])

    assert 'id="no-comments-1"' in logged_client.get("/posts/1/comments", headers=HTMX).text


def test_create_comment_returns_comment_and_updates_count(logged_client, api):
    api.on("POST", "/posts/1/comments", status=201, json=make_comment(9, content="valeu"))
    api.on("GET", "/posts/1", json=make_post(1, comments=3))

    response = logged_client.post("/posts/1/comments", data={"content": " valeu "}, headers=HTMX)

    assert response.status_code == 200
    html = response.text
    assert 'id="comment-9"' in html and "valeu" in html
    assert 'id="comment-count-1" class="chip-count bump" hx-swap-oob="true">3<' in html
    assert 'id="no-comments-1" hx-swap-oob="delete"' in html
    assert api.last_json("POST", "/posts/1/comments") == {"content": "valeu"}


def test_blank_comment_shows_flash(logged_client, api):
    response = logged_client.post("/posts/1/comments", data={"content": "   "}, headers=HTMX)

    assert response.status_code == 422
    assert response.headers["HX-Retarget"] == "#flash"


def test_delete_comment_updates_count(logged_client, api):
    api.on("DELETE", "/comments/9", status=204)
    api.on("GET", "/posts/1", json=make_post(1, comments=2))

    response = logged_client.delete("/posts/1/comments/9", headers=HTMX)

    assert response.status_code == 200
    assert 'id="comment-count-1"' in response.text and ">2<" in response.text


def test_profile_page(logged_client, api):
    api.on(
        "GET",
        "/users/bob/profile",
        json={"user": BOB, "posts": 5, "votes_received": 12, "comments": 3},
    )
    api.on("GET", "/posts/", json=[make_post(i, owner=BOB) for i in range(10, 0, -1)])

    response = logged_client.get("/u/bob")

    assert response.status_code == 200
    html = response.text
    assert "Posts de bob" in html
    assert "bob@example.com" not in html
    assert "<dd>5</dd>" in html and "<dd>12</dd>" in html and "<dd>3</dd>" in html
    assert "membro desde 01/01/2026" in html
    assert api.last("GET", "/posts/").url.params["owner_id"] == "2"
    # "Carregar mais" continua filtrando pelo dono do perfil
    assert 'hx-get="/posts?skip=10&search=&owner_id=2"' in html


def test_my_profile_shows_badge(logged_client, api):
    api.on(
        "GET",
        "/users/alice/profile",
        json={"user": ME, "posts": 0, "votes_received": 0, "comments": 0},
    )
    api.on("GET", "/posts/", json=[])

    html = logged_client.get("/u/alice").text

    assert "Seus posts" in html and ">você<" in html
    assert "alice@example.com" in html and "(só você vê)" in html
    assert "Nada por aqui ainda." in html


def test_profile_without_session_redirects(client):
    response = client.get("/u/alice")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_profile_of_missing_user_shows_error_page(logged_client, api):
    api.on(
        "GET", "/users/ninguem/profile", status=404, json={"detail": "User ninguem was not found"}
    )
    api.on("GET", "/posts/", json=[])

    response = logged_client.get("/u/ninguem")

    assert response.status_code == 404
    assert "was not found" in response.text
