from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

# bcrypt só considera os primeiros 72 bytes, e o bcrypt>=5 lança erro acima disso.
MAX_PASSWORD_BYTES = 72


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


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
    owner: UserOut


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
    owner: UserOut


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserOut
    posts: int
    votes_received: int
    comments: int
