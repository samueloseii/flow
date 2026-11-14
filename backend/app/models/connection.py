import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConnectionStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DISCONNECTED = "disconnected"


class ConnectionType(str, enum.Enum):
    HOUSEHOLD = "household"
    SCHOOL = "school"
    CLINIC = "clinic"
    COMMERCIAL = "commercial"
    PUBLIC_TAP = "public_tap"
    INSTITUTION = "institution"
    OTHER = "other"


class Connection(Base):
    """A metered (or flat-rate) service point belonging to a water committee."""

    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    contact_name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    members_count: Mapped[int] = mapped_column(Integer, default=1)
    connection_type: Mapped[ConnectionType] = mapped_column(
        Enum(ConnectionType), default=ConnectionType.HOUSEHOLD
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus), default=ConnectionStatus.ACTIVE
    )
    has_meter: Mapped[bool] = mapped_column(Boolean, default=False)
    outstanding_balance: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    water_committee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("water_committees.id"), index=True
    )
    # Optional grouping (community, reading circuit ...); not part of the hierarchy.
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("communities.id"), nullable=True, index=True
    )
    tariff_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tariffs.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    water_committee: Mapped["WaterCommittee"] = relationship(  # noqa: F821
        back_populates="connections"
    )
    community: Mapped["Community | None"] = relationship(back_populates="connections")  # noqa: F821
    meters: Mapped[list["Meter"]] = relationship(  # noqa: F821
        back_populates="connection", order_by="desc(Meter.created_at)"
    )
    tariff: Mapped["Tariff | None"] = relationship(back_populates="connections")  # noqa: F821

    @property
    def meter(self) -> "Meter | None":  # noqa: F821
        """The meter currently being read; retired meters stay for history."""
        from app.models.meter import MeterStatus

        active = [m for m in self.meters if m.status == MeterStatus.ACTIVE]
        if active:
            return active[0]
        return self.meters[0] if self.meters else None
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="connection")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship(back_populates="connection")  # noqa: F821
