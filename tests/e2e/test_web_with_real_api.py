import re

HTMX = {"HX-Request": "true"}


def _register(client, email: str) -> None:
    username = email.split("@")[0]
    response = client.post(
        "/register", data={"email": email, "username": username, "password": "secret123"}
    )
    assert response.status_code == 303, response.text
    assert "access_token=" in response.headers["set-cookie"]


def _post_id(html: str) -> int:
    return int(re.search(r'id="post-(\d+)"', html).group(1))


def test_full_user_journey(web):
    alice = web()
    _register(alice, "alice@example.com")

    feed = alice.get("/")
    assert feed.status_code == 200
    assert "@alice" in feed.text
    assert 'id="empty-feed"' in feed.text

    created = alice.post(
        "/posts",
        data={"title": "Olá HTMX", "content": "primeiro post", "published": "true"},
        headers=HTMX,
    )
    assert created.status_code == 200, created.text
    post_id = _post_id(created.text)
    assert "Olá HTMX" in created.text

    voted = alice.post(f"/posts/{post_id}/vote", data={"dir": 1}, headers=HTMX)
    assert 'class="vote-count">1<' in voted.text and 'aria-pressed="true"' in voted.text

    # Remover o voto era o bug original (erro 500 na API).
    unvoted = alice.post(f"/posts/{post_id}/vote", data={"dir": 0}, headers=HTMX)
    assert unvoted.status_code == 200, unvoted.text
    assert 'class="vote-count">0<' in unvoted.text and 'aria-pressed="false"' in unvoted.text

    edited = alice.put(
        f"/posts/{post_id}", data={"title": "Editado", "content": "novo texto"}, headers=HTMX
    )
    assert "Editado" in edited.text
    assert "rascunho" in edited.text  # checkbox desmarcado = não publicado

    found = alice.get("/posts", params={"search": "Edit"}, headers=HTMX)
    assert f'id="post-{post_id}"' in found.text
    not_found = alice.get("/posts", params={"search": "nada"}, headers=HTMX)
    assert "Nenhum post encontrado." in not_found.text


def test_other_users_cannot_change_my_posts(web):
    alice = web()
    _register(alice, "alice@example.com")
    post_id = _post_id(
        alice.post("/posts", data={"title": "da alice", "content": "c"}, headers=HTMX).text
    )

    bob = web()
    _register(bob, "bob@example.com")

    feed = bob.get("/").text
    assert "da alice" in feed
    assert f'hx-get="/posts/{post_id}/edit"' not in feed

    forbidden = bob.delete(f"/posts/{post_id}", headers=HTMX)
    assert forbidden.status_code == 403
    assert forbidden.headers["HX-Retarget"] == "#flash"

    # Bob pode votar no post da Alice.
    assert (
        'class="vote-count">1<'
        in bob.post(f"/posts/{post_id}/vote", data={"dir": 1}, headers=HTMX).text
    )

    deleted = alice.delete(f"/posts/{post_id}", headers=HTMX)
    assert deleted.status_code == 200
    assert "da alice" not in alice.get("/").text


def test_duplicate_registration_shows_message(web):
    _register(web(), "alice@example.com")

    response = web().post(
        "/register", data={"email": "alice@example.com", "username": "outra", "password": "x"}
    )

    assert response.status_code == 409
    assert "Já existe uma conta com esse email." in response.text


def test_wrong_password(web):
    _register(web(), "alice@example.com")

    response = web().post("/login", data={"login": "alice", "password": "errada"})

    assert response.status_code == 401
    assert "Usuário, email ou senha inválidos." in response.text


def test_comments_and_profile(web):
    alice = web()
    _register(alice, "alice@example.com")
    post_id = _post_id(
        alice.post("/posts", data={"title": "comentem", "content": "c"}, headers=HTMX).text
    )

    bob = web()
    _register(bob, "bob@example.com")
    created = bob.post(f"/posts/{post_id}/comments", data={"content": "primeiro!"}, headers=HTMX)
    assert created.status_code == 200, created.text
    assert "primeiro!" in created.text
    assert (
        f'id="comment-count-{post_id}" class="chip-count bump" hx-swap-oob="true">1<'
        in created.text
    )
    comment_id = int(re.search(r'id="comment-(\d+)"', created.text).group(1))

    # alice (dona do post) vê o comentário e pode apagá-lo
    panel = alice.get(f"/posts/{post_id}/comments", headers=HTMX).text
    assert "primeiro!" in panel
    assert f'hx-delete="/posts/{post_id}/comments/{comment_id}"' in panel

    # perfil do bob mostra a contagem de comentários
    assert 'href="/u/bob" title="Meu perfil"' in bob.get("/").text
    profile = alice.get("/u/bob").text
    assert "Posts de bob" in profile
    assert re.search(r"<dt>Comentários</dt><dd>1</dd>", profile)

    deleted = alice.delete(f"/posts/{post_id}/comments/{comment_id}", headers=HTMX)
    assert deleted.status_code == 200
    assert ">0<" in deleted.text


def test_username_signup_rules_and_login(web):
    alice = web()
    _register(alice, "alice@example.com")

    # disponibilidade ao vivo, contra a API real
    assert "Esse nome já está em uso." in web().get("/register/check-username?username=ALICE").text
    assert (
        "✓ @alice.2 está disponível" in web().get("/register/check-username?username=alice.2").text
    )

    taken = web().post(
        "/register", data={"email": "x@example.com", "username": "Alice", "password": "pw"}
    )
    assert taken.status_code == 409
    assert "Esse nome de usuário já está em uso." in taken.text

    # login pelo nome de usuário, em qualquer caixa
    response = web().post("/login", data={"login": "ALICE", "password": "secret123"})
    assert response.status_code == 303
