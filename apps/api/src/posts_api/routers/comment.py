from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import posts_schemas as schemas

from .. import models
from ..database import DbSession
from ..oauth2 import CurrentUser

router = APIRouter(tags=["Comments"])


def _get_post_or_404(db: DbSession, post_id: int) -> models.Post:
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"post with id: {post_id} was not found"
        )
    return post


@router.get("/posts/{post_id}/comments", response_model=list[schemas.CommentOut])
def list_comments(post_id: int, db: DbSession, current_user: CurrentUser):
    _get_post_or_404(db, post_id)
    return db.scalars(
        select(models.Comment)
        .where(models.Comment.post_id == post_id)
        .options(selectinload(models.Comment.owner))  # evita uma query por autor
        .order_by(models.Comment.id)
    ).all()


@router.post(
    "/posts/{post_id}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.CommentOut,
)
def create_comment(
    post_id: int, comment: schemas.CommentCreate, db: DbSession, current_user: CurrentUser
):
    _get_post_or_404(db, post_id)
    new_comment = models.Comment(post_id=post_id, owner_id=current_user.id, content=comment.content)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: DbSession, current_user: CurrentUser) -> None:
    comment = db.get(models.Comment, comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"comment with id: {comment_id} was not found",
        )
    # Quem escreveu o comentário ou o dono do post (moderação) podem apagar.
    post_owner_id = db.get(models.Post, comment.post_id).owner_id
    if current_user.id not in (comment.owner_id, post_owner_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform requested action",
        )
    db.delete(comment)
    db.commit()
