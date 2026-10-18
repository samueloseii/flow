import uuid
from datetime import datetime

from pydantic import BaseModel


class WaterCommitteeCreate(BaseModel):
    name: str
    partner_id: uuid.UUID | None = None
    country: str | None = None
    region: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    description: str | None = None


class WaterCommitteeUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    region: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    description: str | None = None


class WaterCommitteeResponse(BaseModel):
    id: uuid.UUID
    name: str
    partner_id: uuid.UUID
    country: str | None
    region: str | None
    contact_name: str | None
    contact_phone: str | None
    description: str | None
    created_at: datetime
    partner_name: str | None = None
    community_count: int = 0
    household_count: int = 0

    class Config:
        from_attributes = True


class CommitteeFinancials(BaseModel):
    water_committee_id: uuid.UUID
    currency: str
    total_billed: float
    total_collected: float
    outstanding: float
    total_expenses: float
    net_position: float
    communities: list[dict]
