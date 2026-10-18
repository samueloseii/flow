import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MeterStatus(str, enum.Enum):
    ACTIVE = "active"
    FAULTY = "faulty"
    REPLACED = "replaced"
    REMOVED = "removed"


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[MeterStatus] = mapped_column(
        Enum(MeterStatus), default=MeterStatus.ACTIVE
    )
    install_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_reading_value: Mapped[float] = mapped_column(Float, default=0.0)
    last_reading_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avg_consumption_m3: Mapped[float] = mapped_column(Float, default=0.0)

    household_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("households.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    household: Mapped["Household"] = relationship(back_populates="meters")  # noqa: F821
    readings: Mapped[list["MeterReading"]] = relationship(
        back_populates="meter", order_by="desc(MeterReading.reading_date)"
    )


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    reading_value: Mapped[float] = mapped_column(Float)
    previous_value: Mapped[float] = mapped_column(Float, default=0.0)
    consumption_m3: Mapped[float] = mapped_column(Float, default=0.0)
    reading_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_estimated: Mapped[bool] = mapped_column(default=False)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Identifier minted by the device that captured the reading offline. A repeated
    # upload of the same identifier returns the original reading instead of a duplicate.
    client_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )

    meter_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meters.id")
    )
    # Set once the reading has been billed, so a bill can show the readings behind it.
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("invoices.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    meter: Mapped["Meter"] = relationship(back_populates="readings")
