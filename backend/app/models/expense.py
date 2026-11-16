import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExpenseCategory(str, enum.Enum):
    MAINTENANCE = "maintenance"
    ADMINISTRATIVE = "administrative"
    OTHER = "other"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    expense_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    description: Mapped[str] = mapped_column(String(255))
    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory), default=ExpenseCategory.OTHER
    )
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    water_committee: Mapped["WaterCommittee"] = relationship(back_populates="expenses")  # noqa: F821
    community: Mapped["Community | None"] = relationship()  # noqa: F821
