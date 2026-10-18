import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Table, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    PARTNER_ADMIN = "partner_admin"
    COMMUNITY_ADMIN = "community_admin"
    OPERATOR = "operator"
    TREASURER = "treasurer"
    READER = "reader"


# Communities an operator is expected to visit (may span several in one committee).
operator_communities = Table(
    "operator_communities",
    Base.metadata,
    Column("user_id", GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "community_id", GUID(), ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True
    ),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.READER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="es")

    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("partners.id"), nullable=True
    )
    water_committee_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("water_committees.id"), nullable=True
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("communities.id"), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    partner: Mapped["Partner | None"] = relationship(back_populates="users")  # noqa: F821
    community: Mapped["Community | None"] = relationship(back_populates="users")  # noqa: F821
    water_committee: Mapped["WaterCommittee | None"] = relationship(  # noqa: F821
        back_populates="users"
    )
    assigned_communities: Mapped[list["Community"]] = relationship(  # noqa: F821
        secondary=operator_communities
    )
