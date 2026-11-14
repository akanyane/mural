"""Helpers dos testes do posts-web (API falsa e dados de exemplo)."""

import json
from datetime import UTC, datetime

import httpx2

ME = {"id": 1, "email": "alice@example.com", "created_at": "2026-01-01T00:00:00Z"}
BOB = {"id": 2, "email": "bob@example.com", "created_at": "2026-01-01T00:00:00Z"}


def make_post(
    post_id: int,
    *,
    title: str = "Um post",
    content: str = "conteúdo",
    owner: dict = ME,
    votes: int = 0,
    voted: bool = False,
    published: bool = True,
    comments: int = 0,
) -> dict:
    """Um item no formato de PostOut, como a API devolve."""
    return {
        "Post": {
            "id": post_id,
            "title": title,
            "content": content,
            "published": published,
            "created_at": datetime(2026, 1, 2, 15, 30, tzinfo=UTC).isoformat(),
            "owner_id": owner["id"],
            "owner": owner,
        },
        "votes": votes,
        "voted": voted,
        "comments": comments,
    }


def make_comment(
    comment_id: int, *, post_id: int = 1, content: str = "boa!", owner: dict = ME
) -> dict:
    return {
        "id": comment_id,
        "content": content,
        "created_at": datetime(2026, 1, 3, 10, 0, tzinfo=UTC).isoformat(),
        "post_id": post_id,
        "owner_id": owner["id"],
        "owner": owner,
    }


class FakeApi:
    """API falsa: respostas configuradas por (método, caminho) e registro das requisições."""

    def __init__(self):
        self.routes: dict[tuple[str, str], tuple[int, object] | Exception] = {}
        self.requests: list[httpx2.Request] = []

    def on(self, method: str, path: str, status: int = 200, json=None) -> None:
        self.routes[(method, path)] = (status, json)

    def fail(self, method: str, path: str, error: Exception) -> None:
        self.routes[(method, path)] = error

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        route = self.routes.get((request.method, request.url.path))
        if route is None:
            return httpx2.Response(500, json={"detail": f"FakeApi: rota não configurada {request}"})
        if isinstance(route, Exception):
            raise route
        status, body = route
        if status == 204:
            return httpx2.Response(204)
        return httpx2.Response(status, json=body)

    def last(self, method: str, path: str) -> httpx2.Request:
        for request in reversed(self.requests):
            if (request.method, request.url.path) == (method, path):
                return request
        raise AssertionError(f"nenhuma requisição {method} {path}")

    def last_json(self, method: str, path: str):
        return json.loads(self.last(method, path).content)


HTMX = {"HX-Request": "true"}
