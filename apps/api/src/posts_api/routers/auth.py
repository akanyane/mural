from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

import posts_schemas as schemas

from .. import models, oauth2, utils
from ..database import DbSession

router = APIRouter(tags=["Authentication"])

# Comparar contra um hash fictício quando o email não existe evita revelar,
# pelo tempo de resposta, quais emails estão cadastrados.
_DUMMY_HASH = utils.hash_password("dummy-password")


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    # Como no Instagram, dá para entrar com o email ou com o nome de usuário.
    login = user_credentials.username.strip()
    if "@" in login.lstrip("@"):
        condition = models.User.email == login
    else:
        condition = models.User.username == schemas.normalize_username(login)
    user = db.scalar(select(models.User).where(condition))

    password_ok = utils.verify_password(
        user_credentials.password, user.password if user else _DUMMY_HASH
    )
    if user is None or not password_ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials")

    return {"access_token": oauth2.create_access_token(user.id), "token_type": "bearer"}
