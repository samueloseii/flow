import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.community import CommunitySize, WaterSystemType


class CommunityCreate(BaseModel):
    name: str
    country: str
    region: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    population: int | None = None
    total_connections: int = 0
    water_system_type: WaterSystemType = WaterSystemType.GRAVITY_FED
    community_size: CommunitySize = CommunitySize.SMALL
    currency: str = "USD"
    tariff_fixed: float = 0.0
    tariff_per_m3: float = 0.0
    description: str | None = None
    partner_id: uuid.UUID | None = None
    water_committee_id: uuid.UUID | None = None


class CommunityUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    population: int | None = None
    total_connections: int | None = None
    water_system_type: WaterSystemType | None = None
    community_size: CommunitySize | None = None
    currency: str | None = None
    tariff_fixed: float | None = None
    tariff_per_m3: float | None = None
    description: str | None = None
    water_committee_id: uuid.UUID | None = None


class CommunityResponse(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    region: str | None
    municipality: str | None
    latitude: float | None
    longitude: float | None
    population: int | None
    total_connections: int
    water_system_type: WaterSystemType
    community_size: CommunitySize
    currency: str
    tariff_fixed: float
    tariff_per_m3: float
    description: str | None
    partner_id: uuid.UUID
    water_committee_id: uuid.UUID | None = None
    water_committee_name: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
