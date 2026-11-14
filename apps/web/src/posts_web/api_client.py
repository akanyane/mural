"""Cliente HTTP da posts-api.

As respostas são validadas com os mesmos modelos que a API usa (posts_schemas):
se o contrato mudar de um lado, os testes do outro quebram.
"""

import httpx2
from pydantic import TypeAdapter

from posts_schemas import (
    CommentOut,
    PostCreate,
    PostOut,
    PostRead,
    PostUpdate,
    Token,
    UserOut,
    UserProfile,
)

_post_list = TypeAdapter(list[PostOut])
_comment_list = TypeAdapter(list[CommentOut])


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _error_detail(response: httpx2.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return response.text or response.reason_phrase
    if isinstance(detail, list):  # erros de validação (422) do FastAPI
        return "; ".join(error.get("msg", "") for error in detail)
    return str(detail)


class ApiClient:
    def __init__(self, http: httpx2.AsyncClient, token: str | None = None):
        self.http = http
        self.token = token

    async def _request(self, method: str, url: str, **kwargs) -> httpx2.Response:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = await self.http.request(method, url, headers=headers, **kwargs)
        if response.is_error:
            raise ApiError(response.status_code, _error_detail(response))
        return response

    async def login(self, email: str, password: str) -> str:
        response = await self._request(
            "POST", "/login", data={"username": email, "password": password}
        )
        return Token.model_validate(response.json()).access_token

    async def register(self, email: str, password: str) -> UserOut:
        response = await self._request(
            "POST", "/users/", json={"email": email, "password": password}
        )
        return UserOut.model_validate(response.json())

    async def me(self) -> UserOut:
        return UserOut.model_validate((await self._request("GET", "/users/me")).json())

    async def list_posts(
        self, *, search: str = "", skip: int = 0, limit: int = 10, owner_id: int | None = None
    ) -> list[PostOut]:
        params: dict = {"search": search, "skip": skip, "limit": limit}
        if owner_id is not None:
            params["owner_id"] = owner_id
        response = await self._request("GET", "/posts/", params=params)
        return _post_list.validate_python(response.json())

    async def get_post(self, post_id: int) -> PostOut:
        return PostOut.model_validate((await self._request("GET", f"/posts/{post_id}")).json())

    async def create_post(self, post: PostCreate) -> PostRead:
        response = await self._request("POST", "/posts/", json=post.model_dump())
        return PostRead.model_validate(response.json())

    async def update_post(self, post_id: int, post: PostUpdate) -> PostRead:
        response = await self._request("PUT", f"/posts/{post_id}", json=post.model_dump())
        return PostRead.model_validate(response.json())

    async def delete_post(self, post_id: int) -> None:
        await self._request("DELETE", f"/posts/{post_id}")

    async def vote(self, post_id: int, direction: int) -> None:
        await self._request("POST", "/vote/", json={"post_id": post_id, "dir": direction})

    async def profile(self, user_id: int) -> UserProfile:
        response = await self._request("GET", f"/users/{user_id}/profile")
        return UserProfile.model_validate(response.json())

    async def list_comments(self, post_id: int) -> list[CommentOut]:
        response = await self._request("GET", f"/posts/{post_id}/comments")
        return _comment_list.validate_python(response.json())

    async def create_comment(self, post_id: int, content: str) -> CommentOut:
        response = await self._request(
            "POST", f"/posts/{post_id}/comments", json={"content": content}
        )
        return CommentOut.model_validate(response.json())

    async def delete_comment(self, comment_id: int) -> None:
        await self._request("DELETE", f"/comments/{comment_id}")
