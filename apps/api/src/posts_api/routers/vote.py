from fastapi import APIRouter, HTTPException, status

import posts_schemas as schemas

from .. import models
from ..database import DbSession
from ..oauth2 import CurrentUser

router = APIRouter(prefix="/vote", tags=["Vote"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def vote(vote: schemas.Vote, db: DbSession, current_user: CurrentUser):
    if db.get(models.Post, vote.post_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id: {vote.post_id} does not exist",
        )

    found_vote = db.get(models.Vote, {"user_id": current_user.id, "post_id": vote.post_id})

    if vote.dir == 1:
        if found_vote is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"user {current_user.id} has already voted on post {vote.post_id}",
            )
        db.add(models.Vote(post_id=vote.post_id, user_id=current_user.id))
        db.commit()
        return {"message": "successfully added vote"}

    if found_vote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vote does not exist")
    db.delete(found_vote)
    db.commit()
    return {"message": "successfully deleted vote"}
