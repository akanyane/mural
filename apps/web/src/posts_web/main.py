import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx2
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from posts_schemas import PostCreate, PostOut, PostUpdate

from . import filters
from .api_client import ApiClient, ApiError
from .config import settings

BASE_DIR = Path(__file__).resolve().parent
SESSION_COOKIE = "access_token"
PAGE_SIZE = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Um único cliente HTTP (com pool de conexões) para toda a aplicação.
    async with httpx2.AsyncClient(base_url=settings.api_url, timeout=10) as http:
        app.state.http = http
        yield


app = FastAPI(title="Mural", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters.update(
    datetime=filters.full_datetime,
    date=filters.date_only,
    timeago=filters.timeago,
    avatar_hue=filters.avatar_hue,
    handle=filters.handle,
)


# --- dependências -----------------------------------------------------------------


def get_http(request: Request) -> httpx2.AsyncClient:
    return request.app.state.http


def get_api(request: Request, http: Annotated[httpx2.AsyncClient, Depends(get_http)]) -> ApiClient:
    return ApiClient(http, request.cookies.get(SESSION_COOKIE))


Api = Annotated[ApiClient, Depends(get_api)]


# --- helpers ------------------------------------------------------------------------


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def redirect(request: Request, url: str) -> Response:
    # Numa requisição HTMX um 303 seria seguido pelo XHR e o HTML da outra página
    # cairia dentro do alvo; HX-Redirect faz o navegador trocar de página de verdade.
    if is_htmx(request):
        return Response(headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


def flash(request: Request, message: str, status_code: int) -> HTMLResponse:
    """Mensagem de erro para requisições HTMX, exibida em #flash."""
    return templates.TemplateResponse(
        request,
        "partials/flash.html",
        {"message": message},
        status_code=status_code,
        headers={"HX-Retarget": "#flash", "HX-Reswap": "innerHTML"},
    )


def set_session(response: Response, token: str) -> Response:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,  # o JavaScript da página nunca vê o token
        samesite="lax",  # o cookie não vai em POST/PUT/DELETE vindos de outros sites
        secure=settings.cookie_secure,
    )
    return response


def next_skip(posts: list[PostOut], skip: int) -> int | None:
    return skip + PAGE_SIZE if len(posts) == PAGE_SIZE else None


# --- tratamento de erros ----------------------------------------------------------------


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError) -> Response:
    if exc.status_code == 401:  # token ausente, inválido ou expirado
        response = redirect(request, "/login")
        response.delete_cookie(SESSION_COOKIE)
        return response
    if is_htmx(request):
        return flash(request, exc.detail, exc.status_code)
    return templates.TemplateResponse(
        request, "error.html", {"message": exc.detail}, status_code=exc.status_code
    )


@app.exception_handler(httpx2.TransportError)
async def handle_api_unavailable(request: Request, exc: httpx2.TransportError) -> Response:
    message = "A API está indisponível no momento. Tente de novo em instantes."
    if is_htmx(request):
        return flash(request, message, 503)
    return templates.TemplateResponse(request, "error.html", {"message": message}, status_code=503)


# --- autenticação -----------------------------------------------------------------------


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
async def login(
    request: Request,
    api: Api,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    try:
        token = await api.login(email, password)
    except ApiError as exc:
        if exc.status_code not in (403, 422):
            raise
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Email ou senha inválidos.", "email": email},
            status_code=401,
        )
    return set_session(redirect(request, "/"), token)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {})


@app.post("/register")
async def register(
    request: Request,
    api: Api,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    try:
        await api.register(email, password)
    except ApiError as exc:
        if exc.status_code not in (409, 422):
            raise
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": exc.detail, "email": email},
            status_code=exc.status_code,
        )
    token = await api.login(email, password)
    return set_session(redirect(request, "/"), token)


@app.post("/logout")
async def logout(request: Request):
    response = redirect(request, "/login")
    response.delete_cookie(SESSION_COOKIE)
    return response


# --- feed e posts ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def feed(request: Request, api: Api, search: str = ""):
    if api.token is None:
        return redirect(request, "/login")
    me, posts = await asyncio.gather(api.me(), api.list_posts(search=search, limit=PAGE_SIZE))
    return templates.TemplateResponse(
        request,
        "feed.html",
        {"me": me, "posts": posts, "search": search, "skip": 0, "next_skip": next_skip(posts, 0)},
    )


@app.get("/posts", response_class=HTMLResponse)
async def post_list(
    request: Request, api: Api, search: str = "", skip: int = 0, owner_id: int | None = None
):
    """Fragmento usado pela busca e pelo botão "Carregar mais" (feed e perfil)."""
    me, posts = await asyncio.gather(
        api.me(), api.list_posts(search=search, skip=skip, limit=PAGE_SIZE, owner_id=owner_id)
    )
    return templates.TemplateResponse(
        request,
        "partials/post_list.html",
        {
            "me": me,
            "posts": posts,
            "search": search,
            "skip": skip,
            "next_skip": next_skip(posts, skip),
            "owner_id": owner_id,
        },
    )


@app.post("/posts", response_class=HTMLResponse)
async def create_post(
    request: Request,
    api: Api,
    title: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
    published: Annotated[bool, Form()] = False,
):
    if not title.strip() or not content.strip():
        return flash(request, "Título e conteúdo são obrigatórios.", 422)
    me, created = await asyncio.gather(
        api.me(),
        api.create_post(
            PostCreate(title=title.strip(), content=content.strip(), published=published)
        ),
    )
    item = PostOut(Post=created, votes=0, voted=False)
    return templates.TemplateResponse(
        request, "partials/post_created.html", {"me": me, "item": item}
    )


@app.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_card(request: Request, api: Api, post_id: int):
    me, item = await asyncio.gather(api.me(), api.get_post(post_id))
    return templates.TemplateResponse(request, "partials/post_card.html", {"me": me, "item": item})


@app.get("/posts/{post_id}/edit", response_class=HTMLResponse)
async def edit_post_form(request: Request, api: Api, post_id: int):
    item = await api.get_post(post_id)
    return templates.TemplateResponse(request, "partials/post_edit.html", {"post": item.Post})


@app.put("/posts/{post_id}", response_class=HTMLResponse)
async def update_post(
    request: Request,
    api: Api,
    post_id: int,
    title: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
    published: Annotated[bool, Form()] = False,
):
    if not title.strip() or not content.strip():
        return flash(request, "Título e conteúdo são obrigatórios.", 422)
    await api.update_post(
        post_id, PostUpdate(title=title.strip(), content=content.strip(), published=published)
    )
    me, item = await asyncio.gather(api.me(), api.get_post(post_id))
    return templates.TemplateResponse(request, "partials/post_card.html", {"me": me, "item": item})


@app.delete("/posts/{post_id}", response_class=HTMLResponse)
async def delete_post(api: Api, post_id: int):
    await api.delete_post(post_id)
    # 200 com corpo vazio: o HTMX troca o card por "nada" (com 204 ele não faria o swap).
    return HTMLResponse("")


@app.post("/posts/{post_id}/vote", response_class=HTMLResponse)
async def vote(request: Request, api: Api, post_id: int, dir: Annotated[int, Form(ge=0, le=1)]):
    await api.vote(post_id, dir)
    item = await api.get_post(post_id)
    # "toggled" liga a animação do botão só quando o voto acabou de mudar.
    return templates.TemplateResponse(
        request, "partials/vote_button.html", {"item": item, "toggled": True}
    )


# --- comentários -------------------------------------------------------------------


@app.get("/posts/{post_id}/comments", response_class=HTMLResponse)
async def comments_panel(request: Request, api: Api, post_id: int):
    me, item, comments = await asyncio.gather(
        api.me(), api.get_post(post_id), api.list_comments(post_id)
    )
    return templates.TemplateResponse(
        request,
        "partials/comments.html",
        {"me": me, "post": item.Post, "comments": comments},
    )


@app.post("/posts/{post_id}/comments", response_class=HTMLResponse)
async def create_comment(
    request: Request, api: Api, post_id: int, content: Annotated[str, Form()] = ""
):
    if not content.strip():
        return flash(request, "O comentário não pode ficar vazio.", 422)
    me, comment = await asyncio.gather(api.me(), api.create_comment(post_id, content.strip()))
    item = await api.get_post(post_id)  # contagem atualizada para o botão do card
    return templates.TemplateResponse(
        request,
        "partials/comment_created.html",
        {
            "me": me,
            "comment": comment,
            "post_id": post_id,
            "post_owner_id": item.Post.owner_id,
            "count": item.comments,
        },
    )


@app.delete("/posts/{post_id}/comments/{comment_id}", response_class=HTMLResponse)
async def delete_comment(request: Request, api: Api, post_id: int, comment_id: int):
    await api.delete_comment(comment_id)
    item = await api.get_post(post_id)
    return templates.TemplateResponse(
        request, "partials/comment_count.html", {"post_id": post_id, "count": item.comments}
    )


# --- perfil ---------------------------------------------------------------------------


@app.get("/u/{user_id}", response_class=HTMLResponse)
async def profile_page(request: Request, api: Api, user_id: int):
    if api.token is None:
        return redirect(request, "/login")
    me, profile, posts = await asyncio.gather(
        api.me(), api.profile(user_id), api.list_posts(owner_id=user_id, limit=PAGE_SIZE)
    )
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "me": me,
            "profile": profile,
            "posts": posts,
            "search": "",
            "skip": 0,
            "next_skip": next_skip(posts, 0),
            "owner_id": user_id,
        },
    )


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
