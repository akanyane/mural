"""Sessões opacas guardadas no servidor.

O cliente recebe um token aleatório de 256 bits; o banco guarda só o SHA-256 dele
(um vazamento do banco não expõe tokens utilizáveis). Toda requisição autenticada
procura a sessão pelo hash, então apagar a linha revoga a sessão imediatamente.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from . import models
from .config import settings
from .database import DbSession

MAX_USER_AGENT_LENGTH = 512


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    # O SQLite devolve datas sem fuso (gravadas em UTC).
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def hash_token(token: str) -> str:
    # Token aleatório de alta entropia: SHA-256 basta (não precisa de hash lento).
    return hashlib.sha256(token.encode()).hexdigest()


def _expires_at(created_at: datetime, now: datetime) -> datetime:
    idle_limit = now + timedelta(days=settings.session_idle_days)
    absolute_limit = created_at + timedelta(days=settings.session_max_age_days)
    return min(idle_limit, absolute_limit)


def create_session(
    db: DbSession, user: models.User, *, user_agent: str | None, ip_address: str | None
) -> str:
    """Cria a sessão e devolve o token em texto puro (a única vez que ele existe)."""
    now = utcnow()
    # Limpeza oportunista das sessões expiradas deste usuário.
    db.execute(
        delete(models.UserSession).where(
            models.UserSession.user_id == user.id, models.UserSession.expires_at <= now
        )
    )
    token = secrets.token_urlsafe(32)
    db.add(
        models.UserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            created_at=now,
            last_used_at=now,
            expires_at=_expires_at(now, now),
            user_agent=(user_agent or None) and user_agent[:MAX_USER_AGENT_LENGTH],
            ip_address=ip_address or None,
        )
    )
    db.commit()
    return token


def get_valid_session(db: DbSession, token: str) -> models.UserSession | None:
    """Sessão válida para o token, ou None (inexistente, revogada ou expirada)."""
    session = db.scalar(
        select(models.UserSession).where(models.UserSession.token_hash == hash_token(token))
    )
    if session is None:
        return None

    now = utcnow()
    if as_utc(session.expires_at) <= now:
        db.delete(session)
        db.commit()
        return None

    # Expiração deslizante: cada uso empurra o fim da sessão (até o limite absoluto).
    if now - as_utc(session.last_used_at) >= timedelta(minutes=settings.session_touch_minutes):
        session.last_used_at = now
        session.expires_at = _expires_at(as_utc(session.created_at), now)
        db.commit()
    return session
