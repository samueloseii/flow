import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class WaterCommittee(Base):
    """The body that runs one or more community water systems and holds their finances."""

    __tablename__ = "water_committees"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    partner_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("partners.id"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    partner: Mapped["Partner"] = relationship(back_populates="water_committees")  # noqa: F821
    communities: Mapped[list["Community"]] = relationship(  # noqa: F821
        back_populates="water_committee"
    )
    users: Mapped[list["User"]] = relationship(back_populates="water_committee")  # noqa: F821
    tariffs: Mapped[list["Tariff"]] = relationship(back_populates="water_committee")  # noqa: F821
