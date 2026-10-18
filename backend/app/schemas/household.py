import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.household import HouseholdStatus
from app.schemas.billing import InvoiceResponse, PaymentResponse
from app.schemas.meter import MeterReadingResponse, MeterResponse


class HouseholdCreate(BaseModel):
    account_number: str
    head_of_household: str
    address: str | None = None
    phone: str | None = None
    members_count: int = 1
    status: HouseholdStatus = HouseholdStatus.ACTIVE
    has_meter: bool = False
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None
    community_id: uuid.UUID
    tariff_id: uuid.UUID | None = None
    # A meter can be registered together with the account.
    meter_serial_number: str | None = None
    meter_brand: str | None = None
    meter_initial_reading: float = 0.0


class HouseholdUpdate(BaseModel):
    head_of_household: str | None = None
    address: str | None = None
    phone: str | None = None
    members_count: int | None = None
    status: HouseholdStatus | None = None
    has_meter: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None
    tariff_id: uuid.UUID | None = None
    clear_tariff: bool = False


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    account_number: str
    head_of_household: str
    address: str | None
    phone: str | None
    members_count: int
    status: HouseholdStatus
    has_meter: bool
    outstanding_balance: float
    latitude: float | None
    longitude: float | None
    notes: str | None
    community_id: uuid.UUID
    tariff_id: uuid.UUID | None = None
    tariff_name: str | None = None
    created_at: datetime
    updated_at: datetime
    meter_serial_number: str | None = None
    last_reading_value: float | None = None
    last_reading_date: datetime | None = None
    community_name: str | None = None
    currency: str | None = None

    class Config:
        from_attributes = True


class ConsumptionPoint(BaseModel):
    period: str
    consumption_m3: float


class HouseholdDetail(BaseModel):
    household: HouseholdResponse
    consumption_history: list[ConsumptionPoint]
    invoices: list[InvoiceResponse]
    payments: list[PaymentResponse]
    total_billed: float
    total_paid: float
    outstanding: float
    readings: list[MeterReadingResponse] = []
    meters: list[MeterResponse] = []
