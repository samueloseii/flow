import uuid
from datetime import datetime

from pydantic import BaseModel


class PartnerCreate(BaseModel):
    name: str
    country: str
    organization_id: uuid.UUID | None = None
    new_organization_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    description: str | None = None


class PartnerUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    organization_id: uuid.UUID | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    description: str | None = None


class PartnerResponse(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    description: str | None
    created_at: datetime
    communities_count: int = 0
    organization_id: uuid.UUID | None = None
    organization_name: str | None = None

    class Config:
        from_attributes = True


class OrganizationCreate(BaseModel):
    name: str
    country: str | None = None
    description: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    description: str | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    description: str | None
    created_at: datetime
    partners_count: int = 0

    class Config:
        from_attributes = True
