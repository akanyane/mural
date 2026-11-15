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
    ProfileUpdate,
    RevokedSessions,
    SessionOut,
    Token,
    UsernameAvailability,
    UserOut,
    UserProfile,
    UserPublic,
)

_post_list = TypeAdapter(list[PostOut])
_comment_list = TypeAdapter(list[CommentOut])
_user_list = TypeAdapter(list[UserPublic])
_session_list = TypeAdapter(list[SessionOut])


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

    async def _request(
        self, method: str, url: str, *, headers: dict | None = None, **kwargs
    ) -> httpx2.Response:
        headers = dict(headers or {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = await self.http.request(method, url, headers=headers, **kwargs)
        if response.is_error:
            raise ApiError(response.status_code, _error_detail(response))
        return response

    async def login(
        self, login: str, password: str, *, user_agent: str | None = None, ip: str | None = None
    ) -> str:
        """`login` é o email ou o nome de usuário.

        O navegador e o IP de quem está logando são repassados para a API, que os
        mostra na lista de sessões ("Chrome · Windows", IP).
        """
        headers = {}
        if user_agent:
            headers["User-Agent"] = user_agent
        if ip:
            headers["X-Forwarded-For"] = ip
        response = await self._request(
            "POST", "/login", data={"username": login, "password": password}, headers=headers
        )
        return Token.model_validate(response.json()).access_token

    async def register(self, email: str, username: str, password: str) -> UserOut:
        response = await self._request(
            "POST", "/users/", json={"email": email, "username": username, "password": password}
        )
        return UserOut.model_validate(response.json())

    async def me(self) -> UserOut:
        return UserOut.model_validate((await self._request("GET", "/users/me")).json())

    async def list_posts(
        self,
        *,
        search: str = "",
        skip: int = 0,
        limit: int = 10,
        owner_id: int | None = None,
        following: bool = False,
    ) -> list[PostOut]:
        params: dict = {"search": search, "skip": skip, "limit": limit}
        if owner_id is not None:
            params["owner_id"] = owner_id
        if following:
            params["following"] = "true"
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

    async def profile(self, username: str) -> UserProfile:
        response = await self._request("GET", f"/users/{username}/profile")
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

    async def username_available(self, username: str) -> UsernameAvailability:
        response = await self._request(
            "GET", "/users/username-available", params={"username": username}
        )
        return UsernameAvailability.model_validate(response.json())

    async def follow(self, username: str) -> None:
        await self._request("PUT", f"/users/{username}/follow")

    async def unfollow(self, username: str) -> None:
        await self._request("DELETE", f"/users/{username}/follow")

    async def followers(self, username: str, *, skip: int = 0, limit: int = 30) -> list[UserPublic]:
        response = await self._request(
            "GET", f"/users/{username}/followers", params={"skip": skip, "limit": limit}
        )
        return _user_list.validate_python(response.json())

    async def following(self, username: str, *, skip: int = 0, limit: int = 30) -> list[UserPublic]:
        response = await self._request(
            "GET", f"/users/{username}/following", params={"skip": skip, "limit": limit}
        )
        return _user_list.validate_python(response.json())

    async def logout(self) -> None:
        await self._request("POST", "/logout")

    async def sessions(self) -> list[SessionOut]:
        return _session_list.validate_python((await self._request("GET", "/sessions/")).json())

    async def revoke_session(self, session_id: int) -> None:
        await self._request("DELETE", f"/sessions/{session_id}")

    async def revoke_other_sessions(self) -> int:
        response = await self._request("DELETE", "/sessions/others")
        return RevokedSessions.model_validate(response.json()).revoked

    async def update_profile(self, changes: ProfileUpdate) -> UserOut:
        response = await self._request(
            "PATCH", "/users/me/profile", json=changes.model_dump(exclude_unset=True)
        )
        return UserOut.model_validate(response.json())
