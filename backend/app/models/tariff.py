import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class Tariff(Base):
    """A rising block tariff.

    ``base_rate`` is charged every bill and covers consumption up to the first threshold.
    ``thresholds`` are the m³ points where a new price starts; ``rates`` has one more entry
    than ``thresholds``: the price per m³ for each block (the first is usually 0 because
    the base rate already covers it).

    Example: base 3.50, thresholds [10, 15, 20], rates [0, 0.35, 0.50, 0.80].
    """

    __tablename__ = "tariffs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    base_rate: Mapped[float] = mapped_column(Float, default=0.0)
    thresholds: Mapped[list] = mapped_column(JSON, default=list)
    rates: Mapped[list] = mapped_column(JSON, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    water_committee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("water_committees.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    water_committee: Mapped["WaterCommittee"] = relationship(back_populates="tariffs")  # noqa: F821
    households: Mapped[list["Household"]] = relationship(back_populates="tariff")  # noqa: F821

    def charge_for(self, consumption_m3: float) -> tuple[float, float, list[dict]]:
        """Return (fixed, variable, blocks) for a consumption figure."""
        thresholds = [float(t) for t in (self.thresholds or [])]
        rates = [float(r) for r in (self.rates or [])]
        while len(rates) < len(thresholds) + 1:
            rates.append(rates[-1] if rates else 0.0)
        remaining = max(0.0, consumption_m3)
        lower = 0.0
        variable = 0.0
        blocks: list[dict] = []
        for i, rate in enumerate(rates):
            upper = thresholds[i] if i < len(thresholds) else None
            width = remaining if upper is None else max(0.0, min(remaining, upper - lower))
            if width > 0:
                amount = round(width * rate, 2)
                blocks.append({"from_m3": lower, "to_m3": upper, "m3": round(width, 3),
                               "rate": rate, "amount": amount})
                variable += amount
            remaining -= width
            if upper is None or remaining <= 0:
                break
            lower = upper
        return round(self.base_rate, 2), round(variable, 2), blocks
