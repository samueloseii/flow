import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.maintenance import (
    MaintenanceCategory,
    MaintenancePriority,
    MaintenanceStatus,
)


class MaintenanceCreate(BaseModel):
    """An issue reported from the field. Costs are tracked as expenses, not here."""

    title: str
    description: str | None = None
    category: MaintenanceCategory = MaintenanceCategory.OTHER
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    reported_date: datetime
    reported_by: str | None = None
    reported_via_whatsapp: bool = False
    notes: str | None = None
    water_committee_id: uuid.UUID | None = None
    community_id: uuid.UUID | None = None


class MaintenanceUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: MaintenanceCategory | None = None
    priority: MaintenancePriority | None = None
    status: MaintenanceStatus | None = None
    resolved_date: datetime | None = None
    resolved_by: str | None = None
    notes: str | None = None


class MaintenanceResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: MaintenanceCategory
    priority: MaintenancePriority
    status: MaintenanceStatus
    reported_date: datetime
    resolved_date: datetime | None
    reported_by: str | None
    reported_via_whatsapp: bool
    resolved_by: str | None
    notes: str | None
    water_committee_id: uuid.UUID
    community_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    community_name: str | None = None

    class Config:
        from_attributes = True
