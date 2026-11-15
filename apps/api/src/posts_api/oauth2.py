from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from . import models
from .database import DbSession
from .sessions import get_valid_session

# O token agora é uma sessão opaca (não um JWT), mas o transporte continua o mesmo:
# "Authorization: Bearer <token>", obtido em POST /login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_session(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> models.UserSession:
    session = get_valid_session(db, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session


CurrentSession = Annotated[models.UserSession, Depends(get_current_session)]


def get_current_user(session: CurrentSession) -> models.User:
    return session.user


CurrentUser = Annotated[models.User, Depends(get_current_user)]
