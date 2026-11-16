import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class Community(Base):
    """A way of grouping a water committee's connections (a village, a distribution
    line / reading circuit, a bulk-meter group).  Carries no tariff or system data."""

    __tablename__ = "communities"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    water_committee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("water_committees.id"), index=True
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
        back_populates="communities"
    )
    connections: Mapped[list["Connection"]] = relationship(back_populates="community")  # noqa: F821
