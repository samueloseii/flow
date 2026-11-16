import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MaintenancePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MaintenanceStatus(str, enum.Enum):
    REPORTED = "reported"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"


class MaintenanceCategory(str, enum.Enum):
    PIPE_REPAIR = "pipe_repair"
    VALVE_REPLACEMENT = "valve_replacement"
    PUMP_MAINTENANCE = "pump_maintenance"
    TANK_CLEANING = "tank_cleaning"
    METER_REPAIR = "meter_repair"
    CHLORINATION = "chlorination"
    ELECTRICAL = "electrical"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[MaintenanceCategory] = mapped_column(
        Enum(MaintenanceCategory), default=MaintenanceCategory.OTHER
    )
    priority: Mapped[MaintenancePriority] = mapped_column(
        Enum(MaintenancePriority), default=MaintenancePriority.MEDIUM
    )
    status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus), default=MaintenanceStatus.REPORTED
    )
    reported_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    reported_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reported_via_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    water_committee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("water_committees.id"), index=True
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("communities.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    water_committee: Mapped["WaterCommittee"] = relationship(back_populates="maintenance_records")  # noqa: F821
    community: Mapped["Community | None"] = relationship()  # noqa: F821
