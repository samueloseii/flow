import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class UserRole(str, enum.Enum):
    """Super admin sees everything; the others act at their parent entity and below.

    admin: create / edit / delete.  editor: edit only (the treasurer).
    operator: submit meter readings, add or replace meters (water committee level only).
    viewer: read only (the only role allowed at connection level).
    """

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    EDITOR = "editor"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="es")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Where the account sits in the hierarchy (one PARENT row) and, when it is
    # restricted to part of that branch, the CHILD rows it may see.
    relations: Mapped[list["UserRelation"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def parent(self) -> "UserRelation | None":  # noqa: F821
        from app.models.user_relation import RelationType

        return next((r for r in self.relations if r.relation_type == RelationType.PARENT), None)

    @property
    def children(self) -> list["UserRelation"]:  # noqa: F821
        from app.models.user_relation import RelationType

        return [r for r in self.relations if r.relation_type == RelationType.CHILD]
