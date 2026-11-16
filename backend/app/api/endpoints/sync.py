"""Offline sync endpoint — accepts batched meter readings and payments."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, READING_ROLES, require_role
from app.db.session import get_db
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.models.connection import Connection
from app.models.meter import Meter, MeterReading
from app.models.user import User
from app.services.readings import record_reading

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncMeterReading(BaseModel):
    client_id: str
    meter_id: uuid.UUID
    reading_value: float
    reading_date: datetime
    notes: str | None = None
    recorded_by: str | None = None


class SyncPayment(BaseModel):
    client_id: str
    connection_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    amount: float
    currency: str = "USD"
    payment_method: str = "cash"
    payment_date: datetime
    receipt_number: str | None = None
    notes: str | None = None


class SyncRequest(BaseModel):
    readings: list[SyncMeterReading] = []
    payments: list[SyncPayment] = []


class SyncResultItem(BaseModel):
    client_id: str
    server_id: str | None = None
    success: bool
    duplicate: bool = False
    error: str | None = None


class SyncResponse(BaseModel):
    readings: list[SyncResultItem]
    payments: list[SyncResultItem]
    synced_at: datetime


@router.post("/push", response_model=SyncResponse)
def push_offline_data(
    payload: SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*READING_ROLES)),
):
    reading_results: list[SyncResultItem] = []
    payment_results: list[SyncResultItem] = []

    for r in payload.readings:
        try:
            # A device that never saw our response retries the same reading. Return the
            # reading it already created instead of recording the consumption twice.
            existing = (
                db.query(MeterReading).filter(MeterReading.client_id == r.client_id).first()
            )
            if existing:
                reading_results.append(SyncResultItem(
                    client_id=r.client_id,
                    server_id=str(existing.id),
                    success=True,
                    duplicate=True,
                ))
                continue

            meter = db.query(Meter).filter(Meter.id == r.meter_id).first()
            if not meter:
                reading_results.append(SyncResultItem(client_id=r.client_id, success=False, error="Meter not found"))
                continue

            reading = record_reading(
                db,
                meter,
                reading_value=r.reading_value,
                reading_date=r.reading_date,
                notes=r.notes,
                recorded_by=r.recorded_by or current_user.full_name,
                client_id=r.client_id,
            )

            reading_results.append(SyncResultItem(
                client_id=r.client_id, server_id=str(reading.id), success=True,
            ))
        except Exception as e:
            reading_results.append(SyncResultItem(client_id=r.client_id, success=False, error=str(e)))

    for p in payload.payments:
        try:
            if current_user.role not in ADMIN_ROLES:
                payment_results.append(SyncResultItem(
                    client_id=p.client_id,
                    success=False,
                    error="Only administrators and treasurers can record payments",
                ))
                continue

            method = PaymentMethod.CASH
            if p.payment_method == "bank_transfer":
                method = PaymentMethod.BANK_TRANSFER
            elif p.payment_method == "mobile_money":
                method = PaymentMethod.MOBILE_MONEY

            payment = Payment(
                amount=p.amount,
                currency=p.currency,
                payment_method=method,
                payment_date=p.payment_date,
                receipt_number=p.receipt_number,
                notes=p.notes,
                connection_id=p.connection_id,
                invoice_id=p.invoice_id,
            )
            db.add(payment)
            db.flush()

            if p.invoice_id:
                invoice = db.query(Invoice).filter(Invoice.id == p.invoice_id).first()
                if invoice:
                    invoice.amount_paid += p.amount
                    invoice.balance_due = max(0, invoice.total_amount - invoice.amount_paid)
                    if invoice.balance_due == 0:
                        invoice.status = InvoiceStatus.PAID
                    elif invoice.amount_paid > 0:
                        invoice.status = InvoiceStatus.PARTIAL

            connection = db.query(Connection).filter(Connection.id == p.connection_id).first()
            if connection:
                connection.outstanding_balance = max(0, connection.outstanding_balance - p.amount)

            payment_results.append(SyncResultItem(
                client_id=p.client_id, server_id=str(payment.id), success=True,
            ))
        except Exception as e:
            payment_results.append(SyncResultItem(client_id=p.client_id, success=False, error=str(e)))

    db.commit()

    return SyncResponse(
        readings=reading_results,
        payments=payment_results,
        synced_at=datetime.utcnow(),
    )
