import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HouseholdStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DISCONNECTED = "disconnected"


class Household(Base):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    head_of_household: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    members_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[HouseholdStatus] = mapped_column(
        Enum(HouseholdStatus), default=HouseholdStatus.ACTIVE
    )
    has_meter: Mapped[bool] = mapped_column(Boolean, default=False)
    outstanding_balance: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    community_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("communities.id")
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

    community: Mapped["Community"] = relationship(back_populates="households")  # noqa: F821
    meters: Mapped[list["Meter"]] = relationship(  # noqa: F821
        back_populates="household", order_by="desc(Meter.created_at)"
    )
    tariff: Mapped["Tariff | None"] = relationship(back_populates="households")  # noqa: F821

    @property
    def meter(self) -> "Meter | None":  # noqa: F821
        """The meter currently being read; retired meters stay for history."""
        from app.models.meter import MeterStatus

        active = [m for m in self.meters if m.status == MeterStatus.ACTIVE]
        if active:
            return active[0]
        return self.meters[0] if self.meters else None
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="household")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship(back_populates="household")  # noqa: F821
