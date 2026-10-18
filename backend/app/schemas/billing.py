import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.billing import InvoiceStatus, PaymentMethod


class InvoiceCreate(BaseModel):
    billing_period_start: datetime
    billing_period_end: datetime
    consumption_m3: float = 0.0
    fixed_charge: float = 0.0
    variable_charge: float = 0.0
    total_amount: float = 0.0
    currency: str = "USD"
    due_date: datetime
    household_id: uuid.UUID
    notes: str | None = None


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    billing_period_start: datetime
    billing_period_end: datetime
    consumption_m3: float
    fixed_charge: float
    variable_charge: float
    total_amount: float
    amount_paid: float
    balance_due: float
    currency: str
    status: InvoiceStatus
    due_date: datetime
    months_overdue: int
    notes: str | None
    household_id: uuid.UUID
    created_at: datetime
    household_name: str | None = None
    account_number: str | None = None
    community_id: uuid.UUID | None = None
    tariff_name: str | None = None

    class Config:
        from_attributes = True


class InvoiceGenerateRequest(BaseModel):
    community_id: uuid.UUID | None = None
    water_committee_id: uuid.UUID | None = None
    billing_period_start: datetime
    billing_period_end: datetime
    due_date: datetime


class InvoiceGenerateResult(BaseModel):
    created: int
    skipped_existing: int
    skipped_no_reading: int
    skipped_no_tariff: int = 0
    invoices: list[InvoiceResponse]


class PaymentCreate(BaseModel):
    amount: float
    currency: str = "USD"
    payment_method: PaymentMethod = PaymentMethod.CASH
    payment_date: datetime
    receipt_number: str | None = None
    recorded_by: str | None = None
    notes: str | None = None
    household_id: uuid.UUID
    invoice_id: uuid.UUID | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    amount: float
    currency: str
    payment_method: PaymentMethod
    payment_date: datetime
    receipt_number: str | None
    recorded_by: str | None
    notes: str | None
    household_id: uuid.UUID
    invoice_id: uuid.UUID | None
    created_at: datetime
    household_name: str | None = None
    account_number: str | None = None
    invoice_number: str | None = None

    class Config:
        from_attributes = True
