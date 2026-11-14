import uuid
from datetime import datetime

from pydantic import BaseModel


class CommunityCreate(BaseModel):
    name: str
    country: str
    region: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    population: int | None = None
    description: str | None = None
    water_committee_id: uuid.UUID | None = None


class CommunityUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    population: int | None = None
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
    description: str | None
    water_committee_id: uuid.UUID
    water_committee_name: str | None = None
    connection_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
