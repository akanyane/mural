# Mural

## An empowering solution that enables users to seamlessly share their thoughts and engage with content in a social environment. Users post texts, vote on each other's posts and search the feed.

## Technologies
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)
![HTMX](https://img.shields.io/badge/htmx-%233366CC.svg?style=for-the-badge&logo=htmx&logoColor=white)
![uv](https://img.shields.io/badge/uv-%23DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white)
![Git](https://img.shields.io/badge/git-%23F05033.svg?style=for-the-badge&logo=git&logoColor=white)
![GitHub](https://img.shields.io/badge/github-%23121011.svg?style=for-the-badge&logo=github&logoColor=white)

## Monorepo layout

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): one `uv.lock`, one `.venv`, three packages.

```
apps/
  api/        posts-api      FastAPI + SQLAlchemy + Alembic (SQLite by default), server-side sessions
  web/        posts-web      FastAPI + Jinja2 + HTMX frontend; talks to the API over HTTP
packages/
  schemas/    posts-schemas  Pydantic models shared by both apps (the API contract)
tests/
  e2e/        web + real API wired in-memory (ASGITransport + temporary SQLite)
```

The web app never touches the database: it calls the API with `httpx2`, keeps the session token
in an `HttpOnly`, `SameSite=Lax` cookie and validates every response with `posts-schemas`.

### Auth model

- **`users`** holds only authentication data (e-mail, bcrypt password hash) and is never exposed
  publicly. **`profiles`** holds public data (`username`, `display_name`, `bio`) with the same id
  (1:1, `ON DELETE CASCADE`), similar to Supabase's `auth.users` / `public.profiles`.
- **Sessions are opaque and server-side.** Login returns a random 256-bit token, and the
  `sessions` table stores only its SHA-256 hash. Every authenticated request looks the session up,
  so logging out or revoking a session (`DELETE /sessions/{id}`, `DELETE /sessions/others`) takes
  effect immediately. There are no JWTs and no refresh tokens.
- **Expiration is sliding:** a session expires after 30 days without use, with a hard limit of
  90 days. Both limits are configurable.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-packages                       # install every workspace member + dev tools

cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env

# API on :8000 (creates apps/api/posts.db)
cd apps/api && uv run alembic upgrade head && uv run uvicorn posts_api.main:app --reload

# Web on :8001 (in another terminal)
cd apps/web && uv run uvicorn posts_web.main:app --reload --port 8001
```

- Frontend: http://localhost:8001
- API docs: http://localhost:8000/docs

Adding a dependency to one package: `uv add --package posts-web <lib>`.

### Tests and lint

```bash
uv run pytest            # api + web + e2e
uv run pytest apps/web   # just one package
uv run ruff check .
uv run ruff format .
```

## Releases

Versioning is automated by [release-please](https://github.com/googleapis/release-please)
(`.github/workflows/release-please.yml`). The whole monorepo shares **one version** and **one
tag** (`vX.Y.Z`): `version.txt`, the three `pyproject.toml` files and `uv.lock` are always
bumped together, and there is a single `CHANGELOG.md` at the root.

1. Write commits following [Conventional Commits](https://www.conventionalcommits.org/):
   `feat(web): ...`, `fix(api): ...`, `feat(api)!: ...` for breaking changes.
2. On every push to `main`, release-please opens/updates a release PR with the next version and
   changelog. A second job then pushes a "chore: sync uv.lock" commit to that PR.
3. Wait for that commit, then merge the release PR: it creates the `vX.Y.Z` tag and GitHub release.

While the version is `0.x`, `feat` bumps the minor version and breaking changes do not jump to `1.0`.

## Deploy notes

Each app has its own `Procfile` (the API runs `alembic upgrade head` in the release phase).
SQLite stores data in a local file, so it needs a host with a **persistent disk**: on platforms
with an ephemeral filesystem (e.g. Heroku dynos) the database is wiped on every restart/deploy.
Pointing `DATABASE_URL` at PostgreSQL (plus adding a driver such as `psycopg[binary]`) works
without code changes.
