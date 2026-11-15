from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Row, Select, func, select

import posts_schemas as schemas

from .. import models
from ..database import DbSession
from ..oauth2 import CurrentUser

router = APIRouter(prefix="/posts", tags=["Posts"])


def _posts_query(user_id: int) -> Select:
    """Post + contagem de votos e comentários + se o usuário já votou.

    Subqueries escalares em vez de JOIN + GROUP BY: com dois JOINs (votos e
    comentários) as contagens se multiplicariam.
    """
    post_id = models.Post.id
    votes = (
        select(func.count())
        .select_from(models.Vote)
        .where(models.Vote.post_id == post_id)
        .scalar_subquery()
    )
    comments = (
        select(func.count())
        .select_from(models.Comment)
        .where(models.Comment.post_id == post_id)
        .scalar_subquery()
    )
    voted = (
        select(models.Vote)
        .where(models.Vote.post_id == post_id, models.Vote.user_id == user_id)
        .exists()
    )
    return select(
        models.Post, votes.label("votes"), comments.label("comments"), voted.label("voted")
    )


def _to_post_out(row: Row) -> dict:
    post, votes, comments, voted = row
    return {"Post": post, "votes": votes, "comments": comments, "voted": voted}


def _get_owned_post(db: DbSession, id: int, current_user: models.User) -> models.Post:
    post = db.get(models.Post, id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"post with id: {id} was not found"
        )
    if post.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform requested action",
        )
    return post


@router.get("/", response_model=list[schemas.PostOut])
def get_posts(
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    skip: Annotated[int, Query(ge=0)] = 0,
    search: str = "",
    owner_id: int | None = None,
):
    stmt = (
        _posts_query(current_user.id)
        # autoescape: "%" e "_" na busca são texto literal, não curingas do LIKE.
        .where(models.Post.title.contains(search, autoescape=True))
        # Mais recentes primeiro. Sem ORDER BY a paginação não seria determinística.
        .order_by(models.Post.id.desc())
        .limit(limit)
        .offset(skip)
    )
    if owner_id is not None:
        stmt = stmt.where(models.Post.owner_id == owner_id)
    return [_to_post_out(row) for row in db.execute(stmt).all()]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.PostRead)
def create_post(post: schemas.PostCreate, db: DbSession, current_user: CurrentUser):
    new_post = models.Post(owner_id=current_user.id, **post.model_dump())
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@router.get("/{id}", response_model=schemas.PostOut)
def get_post(id: int, db: DbSession, current_user: CurrentUser):
    row = db.execute(_posts_query(current_user.id).where(models.Post.id == id)).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"post with id: {id} was not found"
        )
    return _to_post_out(row)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(id: int, db: DbSession, current_user: CurrentUser) -> None:
    post = _get_owned_post(db, id, current_user)
    db.delete(post)
    db.commit()


@router.put("/{id}", response_model=schemas.PostRead)
def update_post(
    id: int, updated_post: schemas.PostUpdate, db: DbSession, current_user: CurrentUser
):
    post = _get_owned_post(db, id, current_user)
    for field, value in updated_post.model_dump().items():
        setattr(post, field, value)
    db.commit()
    db.refresh(post)
    return post
