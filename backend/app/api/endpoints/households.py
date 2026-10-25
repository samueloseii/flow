import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, get_current_user, require_role
from app.db.session import get_db
from app.models.billing import Invoice, Payment
from app.models.community import Community
from app.models.household import Household
from app.models.meter import Meter, MeterReading
from app.models.meter import MeterStatus
from app.models.tariff import Tariff
from app.models.user import User
from app.schemas.meter import MeterReadingResponse, MeterResponse
from app.services.scope import can_see_committee, forbid, require_community, require_household, scope_households
from app.schemas.billing import InvoiceResponse, PaymentResponse
from app.schemas.household import (
    ConsumptionPoint,
    HouseholdCreate,
    HouseholdDetail,
    HouseholdResponse,
    HouseholdUpdate,
)

router = APIRouter(prefix="/households", tags=["households"])


def _household_response(
    household: Household,
    meter: Meter | None = None,
    community: Community | None = None,
) -> HouseholdResponse:
    response = HouseholdResponse.model_validate(household)
    if meter:
        response.meter_serial_number = meter.serial_number
        response.last_reading_value = meter.last_reading_value
        response.last_reading_date = meter.last_reading_date
    if community:
        response.community_name = community.name
        response.currency = community.currency
    if household.tariff:
        response.tariff_name = household.tariff.name
    return response


def _check_tariff(db: Session, user: User, household: Household, tariff_id: uuid.UUID) -> None:
    tariff = db.query(Tariff).filter(Tariff.id == tariff_id).first()
    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")
    community = db.query(Community).filter(Community.id == household.community_id).first()
    if community and community.water_committee_id and tariff.water_committee_id != community.water_committee_id:
        raise HTTPException(status_code=400, detail="That tariff belongs to a different water committee")
    if not can_see_committee(db, user, tariff.water_committee_id):
        raise forbid()


@router.get("/", response_model=list[HouseholdResponse])
def list_households(
    community_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Household, Meter, Community)
        .outerjoin(
            Meter, (Meter.household_id == Household.id) & (Meter.status == MeterStatus.ACTIVE)
        )
        .outerjoin(Community, Community.id == Household.community_id)
    )
    query = scope_households(db, current_user, query)
    if community_id:
        query = query.filter(Household.community_id == community_id)
    if status_filter:
        query = query.filter(Household.status == status_filter)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Household.head_of_household.ilike(term),
                Household.account_number.ilike(term),
            )
        )
    rows = query.order_by(Household.account_number).offset(skip).limit(limit).all()
    return [_household_response(h, m, c) for h, m, c in rows]


@router.post("/", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
def create_household(
    payload: HouseholdCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Register a water account. Only administrators may open accounts."""
    require_community(db, current_user, payload.community_id)
    existing = (
        db.query(Household)
        .filter(Household.account_number == payload.account_number)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account number {payload.account_number} is already in use",
        )

    data = payload.model_dump()
    serial_number = data.pop("meter_serial_number")
    brand = data.pop("meter_brand")
    initial_reading = data.pop("meter_initial_reading")

    household = Household(**data)
    household.has_meter = bool(serial_number) or payload.has_meter
    if payload.tariff_id:
        _check_tariff(db, current_user, household, payload.tariff_id)
    db.add(household)
    db.flush()

    meter = None
    if serial_number:
        clash = db.query(Meter).filter(Meter.serial_number == serial_number).first()
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Meter {serial_number} is already registered",
            )
        meter = Meter(
            serial_number=serial_number,
            brand=brand,
            install_date=datetime.now(timezone.utc),
            last_reading_value=initial_reading,
            household_id=household.id,
        )
        db.add(meter)

    db.commit()
    db.refresh(household)
    community = db.query(Community).filter(Community.id == household.community_id).first()
    return _household_response(household, meter, community)


@router.get("/{household_id}", response_model=HouseholdResponse)
def get_household(
    household_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    household = require_household(db, current_user, household_id)
    community = db.query(Community).filter(Community.id == household.community_id).first()
    return _household_response(household, household.meter, community)


@router.get("/{household_id}/detail", response_model=HouseholdDetail)
def get_household_detail(
    household_id: uuid.UUID,
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Account history: consumption trend, bills, payments and raw readings in one call."""
    household = require_household(db, current_user, household_id)

    community = db.query(Community).filter(Community.id == household.community_id).first()
    meter = household.meter

    since = datetime.now(timezone.utc) - timedelta(days=31 * months)
    consumption: list[ConsumptionPoint] = []
    if meter:
        readings = (
            db.query(MeterReading)
            .filter(MeterReading.meter_id == meter.id)
            .filter(MeterReading.reading_date >= since)
            .order_by(MeterReading.reading_date)
            .all()
        )
        by_month: dict[str, float] = {}
        for reading in readings:
            key = reading.reading_date.strftime("%Y-%m")
            by_month[key] = by_month.get(key, 0.0) + reading.consumption_m3
        consumption = [
            ConsumptionPoint(period=period, consumption_m3=round(value, 1))
            for period, value in sorted(by_month.items())
        ]

    invoices = (
        db.query(Invoice)
        .filter(Invoice.household_id == household_id)
        .order_by(Invoice.billing_period_start.desc())
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.household_id == household_id)
        .order_by(Payment.payment_date.desc())
        .all()
    )
    invoice_numbers = {invoice.id: invoice.invoice_number for invoice in invoices}

    invoice_responses = []
    for invoice in invoices:
        response = InvoiceResponse.model_validate(invoice)
        response.household_name = household.head_of_household
        response.account_number = household.account_number
        response.community_id = household.community_id
        invoice_responses.append(response)

    payment_responses = []
    for payment in payments:
        response = PaymentResponse.model_validate(payment)
        response.household_name = household.head_of_household
        response.account_number = household.account_number
        response.invoice_number = invoice_numbers.get(payment.invoice_id)
        payment_responses.append(response)

    total_billed = round(sum(i.total_amount for i in invoices), 2)
    total_paid = round(sum(p.amount for p in payments), 2)

    meter_ids = [m.id for m in household.meters]
    raw_readings = (
        db.query(MeterReading)
        .filter(MeterReading.meter_id.in_(meter_ids))
        .order_by(MeterReading.reading_date.desc())
        .limit(100)
        .all()
        if meter_ids
        else []
    )

    return HouseholdDetail(
        household=_household_response(household, meter, community),
        consumption_history=consumption,
        invoices=invoice_responses,
        payments=payment_responses,
        total_billed=total_billed,
        total_paid=total_paid,
        outstanding=round(sum(i.balance_due for i in invoices), 2),
        readings=[MeterReadingResponse.model_validate(r) for r in raw_readings],
        meters=[MeterResponse.model_validate(m) for m in household.meters],
    )


@router.patch("/{household_id}", response_model=HouseholdResponse)
def update_household(
    household_id: uuid.UUID,
    payload: HouseholdUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    household = require_household(db, current_user, household_id)
    data = payload.model_dump(exclude_unset=True)
    clear_tariff = data.pop("clear_tariff", False)
    if clear_tariff:
        data["tariff_id"] = None
    elif data.get("tariff_id"):
        _check_tariff(db, current_user, household, data["tariff_id"])
    for field, value in data.items():
        setattr(household, field, value)
    db.commit()
    db.refresh(household)
    community = db.query(Community).filter(Community.id == household.community_id).first()
    return _household_response(household, household.meter, community)


@router.delete("/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(
    household_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Remove an account and everything recorded against it."""
    household = require_household(db, current_user, household_id)
    meter_ids = [
        meter_id
        for (meter_id,) in db.query(Meter.id).filter(Meter.household_id == household_id).all()
    ]
    if meter_ids:
        db.query(MeterReading).filter(MeterReading.meter_id.in_(meter_ids)).delete(
            synchronize_session=False
        )
    db.query(Payment).filter(Payment.household_id == household_id).delete(
        synchronize_session=False
    )
    db.query(Invoice).filter(Invoice.household_id == household_id).delete(
        synchronize_session=False
    )
    db.query(Meter).filter(Meter.household_id == household_id).delete(synchronize_session=False)
    db.delete(household)
    db.commit()
