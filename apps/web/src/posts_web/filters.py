"""Filtros Jinja usados pelos templates."""

import hashlib
from datetime import UTC, datetime


def _as_utc(value: datetime) -> datetime:
    # O SQLite devolve datas sem fuso (em UTC); trate-as como UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def full_datetime(value: datetime) -> str:
    return _as_utc(value).strftime("%d/%m/%Y %H:%M")


def date_only(value: datetime) -> str:
    return _as_utc(value).strftime("%d/%m/%Y")


def timeago(value: datetime, now: datetime | None = None) -> str:
    """Tempo relativo curto: "agora", "há 5 min", "há 3 h", "ontem", "há 4 dias" ou a data."""
    seconds = ((now or datetime.now(UTC)) - _as_utc(value)).total_seconds()
    if seconds < 60:
        return "agora"
    if seconds < 3600:
        return f"há {int(seconds // 60)} min"
    if seconds < 86400:
        return f"há {int(seconds // 3600)} h"
    days = int(seconds // 86400)
    if days == 1:
        return "ontem"
    if days < 7:
        return f"há {days} dias"
    return _as_utc(value).strftime("%d/%m/%Y")


def avatar_hue(name: str) -> int:
    """Cor estável por usuário (0-359), derivada do nome de usuário."""
    return int(hashlib.md5(name.lower().encode()).hexdigest(), 16) % 360
