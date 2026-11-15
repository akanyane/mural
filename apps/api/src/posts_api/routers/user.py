from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import posts_schemas as schemas

from .. import models, utils
from ..database import DbSession
from ..oauth2 import CurrentUser

router = APIRouter(prefix="/users", tags=["Users"])


def _email_taken(email: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail=f"User with email {email} already exists"
    )


def _username_taken(username: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail=f"Username {username} is already taken"
    )


def _username_exists(db: DbSession, username: str) -> bool:
    return db.scalar(select(models.User.id).where(models.User.username == username)) is not None


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: DbSession):
    # user.username já chega normalizado (minúsculas) e validado pelo schema.
    if db.scalar(select(models.User.id).where(models.User.email == user.email)) is not None:
        raise _email_taken(user.email)
    if _username_exists(db, user.username):
        raise _username_taken(user.username)

    new_user = models.User(
        email=user.email, username=user.username, password=utils.hash_password(user.password)
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Corrida entre duas requisições cadastrando o mesmo email/usuário.
        db.rollback()
        if _username_exists(db, user.username):
            raise _username_taken(user.username) from None
        raise _email_taken(user.email) from None
    db.refresh(new_user)
    return new_user


# As rotas com caminho fixo vêm antes de "/{id}".
@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: CurrentUser):
    return current_user


@router.get("/username-available", response_model=schemas.UsernameAvailability)
def username_available(username: str, db: DbSession):
    """Público: usado no cadastro, antes de a pessoa ter conta."""
    normalized = schemas.normalize_username(username)
    if reason := schemas.username_error(normalized):
        return {"username": normalized, "available": False, "reason": reason}
    if _username_exists(db, normalized):
        return {"username": normalized, "available": False, "reason": "Esse nome já está em uso."}
    return {"username": normalized, "available": True}


@router.get("/{id}", response_model=schemas.UserOut)
def get_user(id: int, db: DbSession):
    user = db.get(models.User, id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id: {id} was not found"
        )
    return user


@router.get("/{username}/profile", response_model=schemas.UserProfile)
def get_profile(username: str, db: DbSession, current_user: CurrentUser):
    normalized = schemas.normalize_username(username)
    user = db.scalar(select(models.User).where(models.User.username == normalized))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {normalized} was not found"
        )

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    return {
        "user": user,
        "posts": count(
            select(func.count()).select_from(models.Post).where(models.Post.owner_id == user.id)
        ),
        "votes_received": count(
            select(func.count())
            .select_from(models.Vote)
            .join(models.Post, models.Vote.post_id == models.Post.id)
            .where(models.Post.owner_id == user.id)
        ),
        "comments": count(
            select(func.count())
            .select_from(models.Comment)
            .where(models.Comment.owner_id == user.id)
        ),
    }
