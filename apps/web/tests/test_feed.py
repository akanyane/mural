import httpx2
from web_helpers import BOB, HTMX, make_post


def test_feed_renders_posts_with_owner_actions_only_on_own_posts(logged_client, api):
    api.on("GET", "/posts/", json=[make_post(2, owner=BOB), make_post(1, title="Meu post")])

    response = logged_client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "Meu post" in html and "@bob" in html
    assert "bob@example.com" not in html  # email não aparece para os outros
    assert 'hx-get="/posts/1/edit"' in html
    assert 'hx-get="/posts/2/edit"' not in html
    assert "02/01/2026 15:30" in html
    # O token do cookie é repassado para a API como Bearer.
    assert api.last("GET", "/posts/").headers["Authorization"] == "Bearer token-da-alice"


def test_feed_escapes_user_content(logged_client, api):
    api.on("GET", "/posts/", json=[make_post(1, title="<script>alert(1)</script>")])

    html = logged_client.get("/").text

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_empty_feed_message(logged_client, api):
    api.on("GET", "/posts/", json=[])

    assert 'id="empty-feed"' in logged_client.get("/").text


def test_search_returns_only_the_list_fragment(logged_client, api):
    api.on("GET", "/posts/", json=[make_post(1, title="python")])

    response = logged_client.get("/posts", params={"search": "py"}, headers=HTMX)

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "python" in response.text
    params = api.last("GET", "/posts/").url.params
    assert (params["search"], params["skip"], params["limit"]) == ("py", "0", "10")


def test_load_more_button_appears_only_when_page_is_full(logged_client, api):
    api.on("GET", "/posts/", json=[make_post(i) for i in range(10, 0, -1)])
    full = logged_client.get("/posts", params={"search": "a b", "skip": 10}, headers=HTMX).text

    api.on("GET", "/posts/", json=[make_post(1)])
    partial = logged_client.get("/posts", params={"skip": 10}, headers=HTMX).text

    assert 'hx-get="/posts?skip=20&search=a%20b"' in full
    assert "Carregar mais" not in partial


def test_create_post_returns_card_and_removes_empty_message(logged_client, api):
    created = make_post(5, title="Novo")["Post"]
    api.on("POST", "/posts/", status=201, json=created)

    response = logged_client.post(
        "/posts", data={"title": " Novo ", "content": "texto", "published": "true"}, headers=HTMX
    )

    assert response.status_code == 200
    assert 'id="post-5"' in response.text
    assert 'id="empty-feed" hx-swap-oob="delete"' in response.text
    assert api.last_json("POST", "/posts/") == {
        "title": "Novo",
        "content": "texto",
        "published": True,
    }


def test_create_post_unchecked_published_sends_false(logged_client, api):
    api.on("POST", "/posts/", status=201, json=make_post(5, published=False)["Post"])

    logged_client.post("/posts", data={"title": "t", "content": "c"}, headers=HTMX)

    assert api.last_json("POST", "/posts/")["published"] is False


def test_create_post_with_blank_title_shows_flash(logged_client, api):
    response = logged_client.post("/posts", data={"title": "  ", "content": "c"}, headers=HTMX)

    assert response.status_code == 422
    assert response.headers["HX-Retarget"] == "#flash"
    assert "obrigatórios" in response.text
    assert not any(r.method == "POST" for r in api.requests)


def test_vote_sends_direction_and_renders_updated_button(logged_client, api):
    api.on("POST", "/vote/", status=201, json={"message": "successfully added vote"})
    api.on("GET", "/posts/1", json=make_post(1, votes=3, voted=True))

    response = logged_client.post("/posts/1/vote", data={"dir": 1}, headers=HTMX)

    assert response.status_code == 200
    assert api.last_json("POST", "/vote/") == {"post_id": 1, "dir": 1}
    html = response.text
    assert 'class="vote-count">3<' in html
    assert """hx-vals='{"dir": 0}'""" in html  # o próximo clique remove o voto
    assert 'aria-pressed="true"' in html


def test_vote_conflict_shows_flash(logged_client, api):
    api.on("POST", "/vote/", status=409, json={"detail": "user 1 has already voted on post 1"})

    response = logged_client.post("/posts/1/vote", data={"dir": 1}, headers=HTMX)

    assert response.status_code == 409
    assert response.headers["HX-Retarget"] == "#flash"
    assert "already voted" in response.text


def test_invalid_vote_direction_is_rejected(logged_client):
    assert logged_client.post("/posts/1/vote", data={"dir": 5}, headers=HTMX).status_code == 422


def test_edit_form_and_update(logged_client, api):
    api.on("GET", "/posts/1", json=make_post(1, title="Antigo"))
    form = logged_client.get("/posts/1/edit", headers=HTMX).text
    assert 'hx-put="/posts/1"' in form and 'value="Antigo"' in form

    api.on("PUT", "/posts/1", json=make_post(1, title="Novo")["Post"])
    api.on("GET", "/posts/1", json=make_post(1, title="Novo"))
    response = logged_client.put("/posts/1", data={"title": "Novo", "content": "c"}, headers=HTMX)

    assert response.status_code == 200
    assert "Novo" in response.text
    assert api.last_json("PUT", "/posts/1") == {"title": "Novo", "content": "c", "published": False}


def test_update_someone_elses_post_shows_flash(logged_client, api):
    api.on("PUT", "/posts/2", status=403, json={"detail": "Not authorized"})

    response = logged_client.put("/posts/2", data={"title": "x", "content": "y"}, headers=HTMX)

    assert response.status_code == 403
    assert response.headers["HX-Retarget"] == "#flash"


def test_delete_post_returns_empty_200(logged_client, api):
    api.on("DELETE", "/posts/1", status=204)

    response = logged_client.delete("/posts/1", headers=HTMX)

    assert response.status_code == 200
    assert response.text == ""


def test_api_unavailable_shows_friendly_error(logged_client, api):
    api.fail("GET", "/users/me", httpx2.ConnectError("connection refused"))
    api.fail("GET", "/posts/", httpx2.ConnectError("connection refused"))

    response = logged_client.get("/")

    assert response.status_code == 503
    assert "indisponível" in response.text
