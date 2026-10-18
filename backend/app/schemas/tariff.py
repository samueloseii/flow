import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


class TariffBase(BaseModel):
    name: str
    description: str | None = None
    currency: str = "USD"
    base_rate: float = 0.0
    thresholds: list[float] = []
    rates: list[float] = []
    is_default: bool = False

    @field_validator("thresholds")
    @classmethod
    def ascending(cls, v: list[float]) -> list[float]:
        if any(b <= a for a, b in zip(v, v[1:])):
            raise ValueError("Thresholds must increase")
        if any(t <= 0 for t in v):
            raise ValueError("Thresholds must be above 0")
        return v

    @model_validator(mode="after")
    def rates_match(self):
        if len(self.rates) != len(self.thresholds) + 1:
            raise ValueError("Give one rate per block: one more rate than thresholds")
        if any(r < 0 for r in self.rates) or self.base_rate < 0:
            raise ValueError("Rates cannot be negative")
        return self


class TariffCreate(TariffBase):
    water_committee_id: uuid.UUID


class TariffUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    currency: str | None = None
    base_rate: float | None = None
    thresholds: list[float] | None = None
    rates: list[float] | None = None
    is_default: bool | None = None


class TariffResponse(TariffBase):
    id: uuid.UUID
    water_committee_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    household_count: int = 0

    class Config:
        from_attributes = True


class TariffPreview(BaseModel):
    consumption_m3: float
    fixed_charge: float
    variable_charge: float
    total: float
    blocks: list[dict]
