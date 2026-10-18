import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, get_current_user, require_role
from app.db.session import get_db
from app.models.billing import Invoice, InvoiceStatus, Payment
from app.models.community import Community
from app.models.household import Household, HouseholdStatus
from app.models.meter import MeterReading
from app.models.tariff import Tariff
from app.models.user import User
from app.schemas.meter import MeterReadingResponse
from app.services.scope import require_community, require_household, require_committee, scope_households
from app.schemas.billing import (
    InvoiceCreate,
    InvoiceGenerateRequest,
    InvoiceGenerateResult,
    InvoiceResponse,
    PaymentCreate,
    PaymentResponse,
)

router = APIRouter(prefix="/billing", tags=["billing"])

UNPAID_STATUSES = (InvoiceStatus.PENDING, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE)


def _generate_invoice_number(db: Session) -> str:
    count = db.query(Invoice).count()
    return f"INV-{count + 1:06d}"


def _apply_to_invoice(invoice: Invoice, amount: float) -> None:
    invoice.amount_paid = round(invoice.amount_paid + amount, 2)
    invoice.balance_due = round(max(0.0, invoice.total_amount - invoice.amount_paid), 2)
    if invoice.balance_due == 0:
        invoice.status = InvoiceStatus.PAID
    elif invoice.amount_paid > 0:
        invoice.status = InvoiceStatus.PARTIAL


def _invoice_response(invoice: Invoice, household: Household | None) -> InvoiceResponse:
    response = InvoiceResponse.model_validate(invoice)
    if household:
        response.household_name = household.head_of_household
        response.account_number = household.account_number
        response.community_id = household.community_id
    return response


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    household_id: uuid.UUID | None = Query(None),
    community_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    unpaid_only: bool = Query(False),
    period_start: datetime | None = Query(None),
    period_end: datetime | None = Query(None),
    search: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Invoice, Household).join(Household, Invoice.household_id == Household.id)
    query = scope_households(db, current_user, query)
    if household_id:
        query = query.filter(Invoice.household_id == household_id)
    if community_id:
        query = query.filter(Household.community_id == community_id)
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    if unpaid_only:
        query = query.filter(Invoice.status.in_(UNPAID_STATUSES))
    if period_start:
        query = query.filter(Invoice.billing_period_end >= period_start)
    if period_end:
        query = query.filter(Invoice.billing_period_start <= period_end)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Household.head_of_household.ilike(term),
                Household.account_number.ilike(term),
                Invoice.invoice_number.ilike(term),
            )
        )
    rows = (
        query.order_by(Invoice.billing_period_start.desc(), Household.account_number)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_invoice_response(invoice, household) for invoice, household in rows]


@router.post("/invoices/generate", response_model=InvoiceGenerateResult)
def generate_invoices(
    payload: InvoiceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Bill every active household with readings in the period.

    Each household is charged on its own tariff (or the committee's default tariff).
    Communities without any tariff fall back to their fixed + per-m³ rates.
    The readings used are stamped with the bill so they can be traced later.
    """
    if payload.water_committee_id:
        require_committee(db, current_user, payload.water_committee_id)
        communities = (
            db.query(Community)
            .filter(Community.water_committee_id == payload.water_committee_id)
            .all()
        )
    elif payload.community_id:
        communities = [require_community(db, current_user, payload.community_id)]
    else:
        raise HTTPException(status_code=400, detail="Choose a community or a water committee")

    created: list[Invoice] = []
    skipped_existing = 0
    skipped_no_reading = 0
    skipped_no_tariff = 0

    for community in communities:
        default_tariff = None
        if community.water_committee_id:
            default_tariff = (
                db.query(Tariff)
                .filter(Tariff.water_committee_id == community.water_committee_id)
                .filter(Tariff.is_default.is_(True))
                .first()
            )
        households = (
            db.query(Household)
            .filter(Household.community_id == community.id)
            .filter(Household.status == HouseholdStatus.ACTIVE)
            .order_by(Household.account_number)
            .all()
        )
        for household in households:
            already = (
                db.query(Invoice)
                .filter(Invoice.household_id == household.id)
                .filter(Invoice.billing_period_start == payload.billing_period_start)
                .first()
            )
            if already:
                skipped_existing += 1
                continue

            meter_ids = [m.id for m in household.meters]
            readings = (
                db.query(MeterReading)
                .filter(MeterReading.meter_id.in_(meter_ids))
                .filter(MeterReading.invoice_id.is_(None))
                .filter(MeterReading.reading_date >= payload.billing_period_start)
                .filter(MeterReading.reading_date <= payload.billing_period_end)
                .all()
                if meter_ids
                else []
            )
            consumption = round(sum(r.consumption_m3 for r in readings), 3)
            if not readings or consumption <= 0:
                skipped_no_reading += 1
                continue

            tariff = household.tariff or default_tariff
            if tariff:
                fixed, variable, _blocks = tariff.charge_for(consumption)
                currency = tariff.currency
                note = f"Tariff: {tariff.name}"
            elif community.tariff_fixed or community.tariff_per_m3:
                fixed = community.tariff_fixed
                variable = round(consumption * community.tariff_per_m3, 2)
                currency = community.currency
                note = None
            else:
                skipped_no_tariff += 1
                continue
            total = round(fixed + variable, 2)
            invoice = Invoice(
                invoice_number=_generate_invoice_number(db),
                billing_period_start=payload.billing_period_start,
                billing_period_end=payload.billing_period_end,
                consumption_m3=consumption,
                fixed_charge=fixed,
                variable_charge=variable,
                total_amount=total,
                balance_due=total,
                currency=currency,
                due_date=payload.due_date,
                household_id=household.id,
                notes=note,
            )
            db.add(invoice)
            db.flush()
            for reading in readings:
                reading.invoice_id = invoice.id
            household.outstanding_balance += total
            created.append(invoice)

    db.commit()
    for invoice in created:
        db.refresh(invoice)

    by_id = {h.id: h for h in households}
    return InvoiceGenerateResult(
        created=len(created),
        skipped_existing=skipped_existing,
        skipped_no_reading=skipped_no_reading,
        skipped_no_tariff=skipped_no_tariff,
        invoices=[_invoice_response(inv, by_id.get(inv.household_id)) for inv in created],
    )


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    invoice = Invoice(
        invoice_number=_generate_invoice_number(db),
        billing_period_start=payload.billing_period_start,
        billing_period_end=payload.billing_period_end,
        consumption_m3=payload.consumption_m3,
        fixed_charge=payload.fixed_charge,
        variable_charge=payload.variable_charge,
        total_amount=payload.total_amount,
        balance_due=payload.total_amount,
        currency=payload.currency,
        due_date=payload.due_date,
        household_id=payload.household_id,
        notes=payload.notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/payments", response_model=list[PaymentResponse])
def list_payments(
    household_id: uuid.UUID | None = Query(None),
    community_id: uuid.UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Payment, Household, Invoice)
        .join(Household, Payment.household_id == Household.id)
        .outerjoin(Invoice, Payment.invoice_id == Invoice.id)
    )
    query = scope_households(db, current_user, query)
    if household_id:
        query = query.filter(Payment.household_id == household_id)
    if community_id:
        query = query.filter(Household.community_id == community_id)
    rows = (
        query.order_by(Payment.payment_date.desc()).offset(skip).limit(limit).all()
    )
    results = []
    for payment, household, invoice in rows:
        response = PaymentResponse.model_validate(payment)
        response.household_name = household.head_of_household
        response.account_number = household.account_number
        response.invoice_number = invoice.invoice_number if invoice else None
        results.append(response)
    return results


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    require_household(db, current_user, payload.household_id)
    payment = Payment(**payload.model_dump())
    db.add(payment)

    if payload.invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == payload.invoice_id).first()
        if invoice:
            _apply_to_invoice(invoice, payload.amount)
    else:
        # Settle the household's oldest outstanding invoices first.
        outstanding = (
            db.query(Invoice)
            .filter(Invoice.household_id == payload.household_id)
            .filter(Invoice.status.in_(UNPAID_STATUSES))
            .order_by(Invoice.billing_period_end)
            .all()
        )
        remaining = payload.amount
        for invoice in outstanding:
            if remaining <= 0:
                break
            applied = min(remaining, invoice.balance_due)
            _apply_to_invoice(invoice, applied)
            remaining -= applied
            if payment.invoice_id is None:
                payment.invoice_id = invoice.id

    # Update household outstanding balance
    household = db.query(Household).filter(Household.id == payload.household_id).first()
    if household:
        household.outstanding_balance = max(0, household.outstanding_balance - payload.amount)

    db.commit()
    db.refresh(payment)
    return payment


class BillDetail(BaseModel):
    household_name: str
    account_number: str
    community_name: str
    country: str
    currency: str
    invoice_number: str
    period: str
    consumption_m3: float
    fixed_charge: float
    variable_charge: float
    total_amount: float
    amount_paid: float
    balance_due: float
    status: str
    due_date: str
    previous_reading: float | None = None
    current_reading: float | None = None
    tariff_name: str | None = None
    readings: list[MeterReadingResponse] = []


@router.get("/bill/{invoice_id}", response_model=BillDetail)
def get_printable_bill(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    household = db.query(Household).filter(Household.id == invoice.household_id).first()
    community = db.query(Community).filter(Community.id == household.community_id).first() if household else None

    if household:
        require_household(db, current_user, household.id)
    readings = (
        db.query(MeterReading)
        .filter(MeterReading.invoice_id == invoice.id)
        .order_by(MeterReading.reading_date)
        .all()
    )
    if not readings and household:
        # Bills from before readings were linked: fall back to the latest two on the active meter.
        meter = household.meter
        if meter:
            readings = (
                db.query(MeterReading)
                .filter(MeterReading.meter_id == meter.id)
                .filter(MeterReading.reading_date <= invoice.billing_period_end)
                .order_by(MeterReading.reading_date)
                .limit(2)
                .all()
            )

    current_reading = readings[-1].reading_value if readings else None
    previous_reading = readings[0].previous_value if readings else None
    tariff_name = (
        invoice.notes.replace("Tariff: ", "") if invoice.notes and invoice.notes.startswith("Tariff: ") else None
    )

    period_str = f"{invoice.billing_period_start.strftime('%b %d')} - {invoice.billing_period_end.strftime('%b %d, %Y')}"

    return BillDetail(
        household_name=household.head_of_household if household else "Unknown",
        account_number=household.account_number if household else "N/A",
        community_name=community.name if community else "Unknown",
        country=community.country if community else "",
        currency=invoice.currency,
        invoice_number=invoice.invoice_number,
        period=period_str,
        consumption_m3=invoice.consumption_m3,
        fixed_charge=invoice.fixed_charge,
        variable_charge=invoice.variable_charge,
        total_amount=invoice.total_amount,
        amount_paid=invoice.amount_paid,
        balance_due=invoice.balance_due,
        status=invoice.status.value,
        due_date=invoice.due_date.strftime('%b %d, %Y'),
        previous_reading=previous_reading,
        current_reading=current_reading,
        tariff_name=tariff_name,
        readings=[MeterReadingResponse.model_validate(r) for r in readings],
    )


def _recalculate_invoice(db: Session, invoice: Invoice) -> None:
    paid = (
        db.query(func.coalesce(func.sum(Payment.amount), 0.0))
        .filter(Payment.invoice_id == invoice.id)
        .scalar()
    )
    invoice.amount_paid = round(float(paid), 2)
    invoice.balance_due = round(max(0.0, invoice.total_amount - invoice.amount_paid), 2)
    if invoice.balance_due == 0:
        invoice.status = InvoiceStatus.PAID
    elif invoice.amount_paid > 0:
        invoice.status = InvoiceStatus.PARTIAL
    else:
        invoice.status = InvoiceStatus.PENDING


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if db.query(Payment).filter(Payment.invoice_id == invoice_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete the payments on this bill first",
        )
    household = db.query(Household).filter(Household.id == invoice.household_id).first()
    if household:
        require_household(db, current_user, household.id)
        household.outstanding_balance = round(
            max(0.0, household.outstanding_balance - invoice.balance_due), 2
        )
    db.query(MeterReading).filter(MeterReading.invoice_id == invoice_id).update(
        {MeterReading.invoice_id: None}, synchronize_session=False
    )
    db.delete(invoice)
    db.commit()


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Reverse a payment and restore the balances it settled."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    invoice_id = payment.invoice_id
    household_id = payment.household_id
    amount = payment.amount
    db.delete(payment)
    db.flush()
    if invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            _recalculate_invoice(db, invoice)
    household = db.query(Household).filter(Household.id == household_id).first()
    if household:
        household.outstanding_balance = round(household.outstanding_balance + amount, 2)
    db.commit()
