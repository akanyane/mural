from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

import posts_schemas as schemas

from .. import models
from ..database import DbSession
from ..oauth2 import CurrentSession
from ..sessions import utcnow

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("/", response_model=list[schemas.SessionOut])
def list_sessions(db: DbSession, current: CurrentSession):
    """Sessões ativas do usuário, da usada mais recentemente para a mais antiga."""
    rows = db.scalars(
        select(models.UserSession)
        .where(
            models.UserSession.user_id == current.user_id,
            models.UserSession.expires_at > utcnow(),
        )
        .order_by(models.UserSession.last_used_at.desc(), models.UserSession.id.desc())
    ).all()
    return [
        schemas.SessionOut.model_validate(row).model_copy(update={"current": row.id == current.id})
        for row in rows
    ]


# Antes de "/{session_id}".
@router.delete("/others", response_model=schemas.RevokedSessions)
def revoke_other_sessions(db: DbSession, current: CurrentSession):
    """Sai de todos os outros dispositivos; a sessão atual continua."""
    result = db.execute(
        delete(models.UserSession).where(
            models.UserSession.user_id == current.user_id,
            models.UserSession.id != current.id,
        )
    )
    db.commit()
    return {"revoked": result.rowcount}


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(session_id: int, db: DbSession, current: CurrentSession) -> None:
    session = db.get(models.UserSession, session_id)
    # 404 também para sessões de outros usuários: não revela que o id existe.
    if session is None or session.user_id != current.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.delete(session)
    db.commit()
