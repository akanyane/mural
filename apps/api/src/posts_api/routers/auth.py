from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

import posts_schemas as schemas

from .. import models, sessions, utils
from ..database import DbSession
from ..oauth2 import CurrentSession

router = APIRouter(tags=["Authentication"])

# Comparar contra um hash fictício quando o email não existe evita revelar,
# pelo tempo de resposta, quais emails estão cadastrados.
_DUMMY_HASH = utils.hash_password("dummy-password")


def _client_ip(request: Request) -> str | None:
    # Informativo (lista de sessões): atrás do posts-web, o IP real vem em X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


@router.post("/login", response_model=schemas.Token)
def login(
    request: Request,
    user_credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    # Como no Instagram, dá para entrar com o email ou com o nome de usuário.
    login = user_credentials.username.strip()
    if "@" in login.lstrip("@"):
        condition = models.User.email == login
    else:
        condition = models.Profile.username == schemas.normalize_username(login)
    user = db.scalar(select(models.User).join(models.User.profile).where(condition))

    password_ok = utils.verify_password(
        user_credentials.password, user.password if user else _DUMMY_HASH
    )
    if user is None or not password_ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials")

    token = sessions.create_session(
        db, user, user_agent=request.headers.get("user-agent"), ip_address=_client_ip(request)
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(session: CurrentSession, db: DbSession) -> None:
    """Revoga a sessão atual: o token deixa de valer imediatamente."""
    db.delete(session)
    db.commit()
