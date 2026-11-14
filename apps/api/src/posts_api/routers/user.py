from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import posts_schemas as schemas

from .. import models, utils
from ..database import DbSession
from ..oauth2 import CurrentUser

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: DbSession):
    email_taken = HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail=f"User with email {user.email} already exists"
    )
    if db.scalar(select(models.User.id).where(models.User.email == user.email)) is not None:
        raise email_taken

    new_user = models.User(email=user.email, password=utils.hash_password(user.password))
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Corrida entre duas requisições cadastrando o mesmo email.
        db.rollback()
        raise email_taken from None
    db.refresh(new_user)
    return new_user


# Declarada antes de "/{id}" para "me" não ser tratado como id.
@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: CurrentUser):
    return current_user


@router.get("/{id}", response_model=schemas.UserOut)
def get_user(id: int, db: DbSession):
    user = db.get(models.User, id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id: {id} was not found"
        )
    return user


@router.get("/{id}/profile", response_model=schemas.UserProfile)
def get_profile(id: int, db: DbSession, current_user: CurrentUser):
    user = db.get(models.User, id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id: {id} was not found"
        )

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    return {
        "user": user,
        "posts": count(
            select(func.count()).select_from(models.Post).where(models.Post.owner_id == id)
        ),
        "votes_received": count(
            select(func.count())
            .select_from(models.Vote)
            .join(models.Post, models.Vote.post_id == models.Post.id)
            .where(models.Post.owner_id == id)
        ),
        "comments": count(
            select(func.count()).select_from(models.Comment).where(models.Comment.owner_id == id)
        ),
    }
