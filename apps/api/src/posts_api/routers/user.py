from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
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


def _get_user_by_username(db: DbSession, username: str) -> models.User:
    normalized = schemas.normalize_username(username)
    user = db.scalar(select(models.User).where(models.User.username == normalized))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {normalized} was not found"
        )
    return user


def _follow_exists(db: DbSession, follower_id: int, followed_id: int) -> bool:
    key = {"follower_id": follower_id, "followed_id": followed_id}
    return db.get(models.Follow, key) is not None


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
    user = _get_user_by_username(db, username)

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
        "followers": count(
            select(func.count())
            .select_from(models.Follow)
            .where(models.Follow.followed_id == user.id)
        ),
        "following": count(
            select(func.count())
            .select_from(models.Follow)
            .where(models.Follow.follower_id == user.id)
        ),
        "is_following": _follow_exists(db, current_user.id, user.id),
        "follows_you": _follow_exists(db, user.id, current_user.id),
    }


# --- seguir -----------------------------------------------------------------------------
# PUT/DELETE idempotentes: repetir a ação não dá erro, o que simplifica botões de
# "seguir" que podem ser clicados duas vezes ou disparados em paralelo.


@router.put("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def follow(username: str, db: DbSession, current_user: CurrentUser) -> None:
    target = _get_user_by_username(db, username)
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself"
        )
    if _follow_exists(db, current_user.id, target.id):
        return
    db.add(models.Follow(follower_id=current_user.id, followed_id=target.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # outra requisição criou o mesmo follow ao mesmo tempo: já está seguindo


@router.delete("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow(username: str, db: DbSession, current_user: CurrentUser) -> None:
    target = _get_user_by_username(db, username)
    follow = db.get(models.Follow, {"follower_id": current_user.id, "followed_id": target.id})
    if follow is not None:
        db.delete(follow)
        db.commit()


Limit = Annotated[int, Query(ge=1, le=100)]
Skip = Annotated[int, Query(ge=0)]


@router.get("/{username}/followers", response_model=list[schemas.UserPublic])
def list_followers(
    username: str, db: DbSession, current_user: CurrentUser, limit: Limit = 50, skip: Skip = 0
):
    """Quem segue `username` (mais recentes primeiro)."""
    target = _get_user_by_username(db, username)
    return db.scalars(
        select(models.User)
        .join(models.Follow, models.Follow.follower_id == models.User.id)
        .where(models.Follow.followed_id == target.id)
        .order_by(models.Follow.created_at.desc(), models.User.id.desc())
        .limit(limit)
        .offset(skip)
    ).all()


@router.get("/{username}/following", response_model=list[schemas.UserPublic])
def list_following(
    username: str, db: DbSession, current_user: CurrentUser, limit: Limit = 50, skip: Skip = 0
):
    """Quem `username` segue (mais recentes primeiro)."""
    target = _get_user_by_username(db, username)
    return db.scalars(
        select(models.User)
        .join(models.Follow, models.Follow.followed_id == models.User.id)
        .where(models.Follow.follower_id == target.id)
        .order_by(models.Follow.created_at.desc(), models.User.id.desc())
        .limit(limit)
        .offset(skip)
    ).all()
