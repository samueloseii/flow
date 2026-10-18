import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WaterSystemType(str, enum.Enum):
    GRAVITY_FED = "gravity_fed"
    PUMPED = "pumped"
    MIXED = "mixed"


class CommunitySize(str, enum.Enum):
    SMALL = "small"       # < 50 connections
    MEDIUM = "medium"     # 50-200 connections
    LARGE = "large"       # > 200 connections


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_connections: Mapped[int] = mapped_column(Integer, default=0)
    water_system_type: Mapped[WaterSystemType] = mapped_column(
        Enum(WaterSystemType), default=WaterSystemType.GRAVITY_FED
    )
    community_size: Mapped[CommunitySize] = mapped_column(
        Enum(CommunitySize), default=CommunitySize.SMALL
    )
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    tariff_fixed: Mapped[float] = mapped_column(Float, default=0.0)
    tariff_per_m3: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    partner_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("partners.id")
    )
    water_committee_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("water_committees.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    partner: Mapped["Partner"] = relationship(back_populates="communities")  # noqa: F821
    water_committee: Mapped["WaterCommittee | None"] = relationship(  # noqa: F821
        back_populates="communities"
    )
    households: Mapped[list["Household"]] = relationship(back_populates="community")  # noqa: F821
    users: Mapped[list["User"]] = relationship(back_populates="community")  # noqa: F821
    maintenance_records: Mapped[list["MaintenanceRecord"]] = relationship(  # noqa: F821
        back_populates="community"
    )
    expenses: Mapped[list["Expense"]] = relationship(back_populates="community")  # noqa: F821
