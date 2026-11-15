from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    """Conta de autenticação (como o auth.users do Supabase): email, senha e sessões.

    Os dados públicos ficam em Profile (1:1, mesmo id). Nada desta tabela é exposto
    publicamente, exceto via as propriedades de conveniência abaixo, que leem do perfil.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # lazy="joined": carregar um usuário já traz o perfil na mesma query.
    profile: Mapped["Profile"] = relationship(
        back_populates="user", lazy="joined", cascade="all, delete-orphan"
    )

    # Atalhos para serializar UserOut/UserPublic direto de um User.
    @property
    def username(self) -> str:
        return self.profile.username

    @property
    def display_name(self) -> str | None:
        return self.profile.display_name

    @property
    def bio(self) -> str | None:
        return self.profile.bio


class Profile(Base):
    """Dados públicos do usuário (como o public.profiles do Supabase).

    A chave primária é o próprio id do usuário (FK para users.id, ON DELETE CASCADE).
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # Único, minúsculo, regras do Instagram (validado em posts_schemas.Username).
    username: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str | None]
    bio: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    content: Mapped[str]
    published: Mapped[bool] = mapped_column(server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    owner: Mapped[User] = relationship()


class Vote(Base):
    __tablename__ = "votes"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    owner: Mapped[User] = relationship()


class Follow(Base):
    """follower_id segue followed_id."""

    __tablename__ = "follows"
    __table_args__ = (CheckConstraint("follower_id != followed_id", name="ck_follows_not_self"),)

    follower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # A chave primária (follower_id, followed_id) já indexa "quem eu sigo";
    # este índice atende "quem me segue".
    followed_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    """Sessão de login no servidor. Apagar a linha revoga a sessão na hora."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # SHA-256 (hex) do token; o token em si nunca é guardado.
    token_hash: Mapped[str] = mapped_column(unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None]
    ip_address: Mapped[str | None]

    user: Mapped[User] = relationship()
