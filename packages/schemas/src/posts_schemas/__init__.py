import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    StringConstraints,
    field_validator,
)

# --- nome de usuário (regras do Instagram) ---------------------------------------------

USERNAME_MAX_LENGTH = 30
_USERNAME_CHARS = re.compile(r"^[a-z0-9._]+$")


def normalize_username(value: str) -> str:
    """Remove espaços nas pontas, um "@" inicial e passa para minúsculas."""
    return value.strip().removeprefix("@").lower()


def username_error(value: str) -> str | None:
    """Motivo pelo qual um nome de usuário (já normalizado) é inválido, ou None.

    Regras do Instagram: até 30 caracteres; só letras sem acento, números, "_" e
    "."; sem ponto no início/fim nem dois pontos seguidos; não pode ser só números.
    """
    if not value:
        return "Escolha um nome de usuário."
    if len(value) > USERNAME_MAX_LENGTH:
        return f"Use no máximo {USERNAME_MAX_LENGTH} caracteres."
    if not _USERNAME_CHARS.match(value):
        return "Use só letras sem acento, números, _ e ."
    if value.startswith(".") or value.endswith("."):
        return "Não pode começar nem terminar com ponto."
    if ".." in value:
        return "Não pode ter dois pontos seguidos."
    if value.isdigit():
        return "Não pode ter só números."
    return None


def _check_username(value: str) -> str:
    if error := username_error(value):
        raise ValueError(error)
    return value


Username = Annotated[
    str,
    BeforeValidator(lambda v: normalize_username(v) if isinstance(v, str) else v),
    AfterValidator(_check_username),
]

# bcrypt só considera os primeiros 72 bytes, e o bcrypt>=5 lança erro acima disso.
MAX_PASSWORD_BYTES = 72


class UserCreate(BaseModel):
    email: EmailStr
    username: Username
    password: str

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
        return value


class UserOut(BaseModel):
    """O próprio usuário (inclui o email). Só para /users/me e o cadastro."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    display_name: str | None = None
    bio: str | None = None
    created_at: datetime


class UserPublic(BaseModel):
    """Perfil público de qualquer usuário (sem email)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None = None
    bio: str | None = None
    created_at: datetime


DISPLAY_NAME_MAX_LENGTH = 50
BIO_MAX_LENGTH = 160


class ProfileUpdate(BaseModel):
    """Campos editáveis do perfil (PATCH: só os enviados mudam)."""

    username: Username | None = None
    display_name: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=DISPLAY_NAME_MAX_LENGTH)
    ] = None
    bio: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=BIO_MAX_LENGTH)
    ] = None


class PostBase(BaseModel):
    title: str
    content: str
    published: bool = True


class PostCreate(PostBase):
    pass


class PostUpdate(PostBase):
    pass


class PostRead(PostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    owner_id: int
    owner: UserPublic


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Post: PostRead
    votes: int
    # Se o usuário autenticado já votou neste post.
    voted: bool = False
    comments: int = 0


class Token(BaseModel):
    access_token: str
    token_type: str


class Vote(BaseModel):
    post_id: int
    dir: Literal[0, 1]


MAX_COMMENT_LENGTH = 1000

CommentContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_COMMENT_LENGTH)
]


class CommentCreate(BaseModel):
    content: CommentContent


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime
    post_id: int
    owner_id: int
    owner: UserPublic


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserPublic
    posts: int
    votes_received: int
    comments: int
    followers: int = 0
    following: int = 0
    # Do ponto de vista do usuário autenticado:
    is_following: bool = False  # eu sigo este usuário
    follows_you: bool = False  # este usuário me segue


class UsernameAvailability(BaseModel):
    username: str
    available: bool
    reason: str | None = None


class SessionOut(BaseModel):
    """Uma sessão de login ativa (sem o token)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    user_agent: str | None = None
    ip_address: str | None = None
    current: bool = False  # é a sessão que fez esta requisição


class RevokedSessions(BaseModel):
    revoked: int
