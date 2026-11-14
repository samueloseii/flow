import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, get_current_user, require_role
from app.db.session import get_db
from app.models.billing import Invoice, Payment
from app.models.community import Community
from app.models.connection import Connection
from app.models.meter import Meter, MeterReading
from app.models.meter import MeterStatus
from app.models.tariff import Tariff
from app.models.user import User
from app.schemas.meter import MeterReadingResponse, MeterResponse
from app.services.scope import can_see_committee, forbid, require_community, require_connection, scope_connections
from app.schemas.billing import InvoiceResponse, PaymentResponse
from app.schemas.connection import (
    ConsumptionPoint,
    ConnectionCreate,
    ConnectionDetail,
    ConnectionResponse,
    ConnectionUpdate,
)

router = APIRouter(prefix="/connections", tags=["connections"])


def _connection_response(
    connection: Connection,
    meter: Meter | None = None,
    community: Community | None = None,
) -> ConnectionResponse:
    response = ConnectionResponse.model_validate(connection)
    if meter:
        response.meter_serial_number = meter.serial_number
        response.last_reading_value = meter.last_reading_value
        response.last_reading_date = meter.last_reading_date
    if community:
        response.community_name = community.name
        response.currency = community.currency
    if connection.tariff:
        response.tariff_name = connection.tariff.name
    return response


def _check_tariff(db: Session, user: User, connection: Connection, tariff_id: uuid.UUID) -> None:
    tariff = db.query(Tariff).filter(Tariff.id == tariff_id).first()
    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")
    community = db.query(Community).filter(Community.id == connection.community_id).first()
    if community and community.water_committee_id and tariff.water_committee_id != community.water_committee_id:
        raise HTTPException(status_code=400, detail="That tariff belongs to a different water committee")
    if not can_see_committee(db, user, tariff.water_committee_id):
        raise forbid()


@router.get("/", response_model=list[ConnectionResponse])
def list_connections(
    community_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Connection, Meter, Community)
        .outerjoin(
            Meter, (Meter.connection_id == Connection.id) & (Meter.status == MeterStatus.ACTIVE)
        )
        .outerjoin(Community, Community.id == Connection.community_id)
    )
    query = scope_connections(db, current_user, query)
    if community_id:
        query = query.filter(Connection.community_id == community_id)
    if status_filter:
        query = query.filter(Connection.status == status_filter)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Connection.contact_name.ilike(term),
                Connection.account_number.ilike(term),
            )
        )
    rows = query.order_by(Connection.account_number).offset(skip).limit(limit).all()
    return [_connection_response(h, m, c) for h, m, c in rows]


@router.post("/", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Register a water account. Only administrators may open accounts."""
    require_community(db, current_user, payload.community_id)
    existing = (
        db.query(Connection)
        .filter(Connection.account_number == payload.account_number)
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

    connection = Connection(**data)
    connection.has_meter = bool(serial_number) or payload.has_meter
    if payload.tariff_id:
        _check_tariff(db, current_user, connection, payload.tariff_id)
    db.add(connection)
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
            connection_id=connection.id,
        )
        db.add(meter)

    db.commit()
    db.refresh(connection)
    community = db.query(Community).filter(Community.id == connection.community_id).first()
    return _connection_response(connection, meter, community)


@router.get("/{connection_id}", response_model=ConnectionResponse)
def get_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    connection = require_connection(db, current_user, connection_id)
    community = db.query(Community).filter(Community.id == connection.community_id).first()
    return _connection_response(connection, connection.meter, community)


@router.get("/{connection_id}/detail", response_model=ConnectionDetail)
def get_connection_detail(
    connection_id: uuid.UUID,
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Account history: consumption trend, bills, payments and raw readings in one call."""
    connection = require_connection(db, current_user, connection_id)

    community = db.query(Community).filter(Community.id == connection.community_id).first()
    meter = connection.meter

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
        .filter(Invoice.connection_id == connection_id)
        .order_by(Invoice.billing_period_start.desc())
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.connection_id == connection_id)
        .order_by(Payment.payment_date.desc())
        .all()
    )
    invoice_numbers = {invoice.id: invoice.invoice_number for invoice in invoices}

    invoice_responses = []
    for invoice in invoices:
        response = InvoiceResponse.model_validate(invoice)
        response.connection_name = connection.contact_name
        response.account_number = connection.account_number
        response.community_id = connection.community_id
        invoice_responses.append(response)

    payment_responses = []
    for payment in payments:
        response = PaymentResponse.model_validate(payment)
        response.connection_name = connection.contact_name
        response.account_number = connection.account_number
        response.invoice_number = invoice_numbers.get(payment.invoice_id)
        payment_responses.append(response)

    total_billed = round(sum(i.total_amount for i in invoices), 2)
    total_paid = round(sum(p.amount for p in payments), 2)

    meter_ids = [m.id for m in connection.meters]
    raw_readings = (
        db.query(MeterReading)
        .filter(MeterReading.meter_id.in_(meter_ids))
        .order_by(MeterReading.reading_date.desc())
        .limit(100)
        .all()
        if meter_ids
        else []
    )

    return ConnectionDetail(
        connection=_connection_response(connection, meter, community),
        consumption_history=consumption,
        invoices=invoice_responses,
        payments=payment_responses,
        total_billed=total_billed,
        total_paid=total_paid,
        outstanding=round(sum(i.balance_due for i in invoices), 2),
        readings=[MeterReadingResponse.model_validate(r) for r in raw_readings],
        meters=[MeterResponse.model_validate(m) for m in connection.meters],
    )


@router.patch("/{connection_id}", response_model=ConnectionResponse)
def update_connection(
    connection_id: uuid.UUID,
    payload: ConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    connection = require_connection(db, current_user, connection_id)
    data = payload.model_dump(exclude_unset=True)
    clear_tariff = data.pop("clear_tariff", False)
    if clear_tariff:
        data["tariff_id"] = None
    elif data.get("tariff_id"):
        _check_tariff(db, current_user, connection, data["tariff_id"])
    for field, value in data.items():
        setattr(connection, field, value)
    db.commit()
    db.refresh(connection)
    community = db.query(Community).filter(Community.id == connection.community_id).first()
    return _connection_response(connection, connection.meter, community)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Remove an account and everything recorded against it."""
    connection = require_connection(db, current_user, connection_id)
    meter_ids = [
        meter_id
        for (meter_id,) in db.query(Meter.id).filter(Meter.connection_id == connection_id).all()
    ]
    if meter_ids:
        db.query(MeterReading).filter(MeterReading.meter_id.in_(meter_ids)).delete(
            synchronize_session=False
        )
    db.query(Payment).filter(Payment.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.query(Invoice).filter(Invoice.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.query(Meter).filter(Meter.connection_id == connection_id).delete(synchronize_session=False)
    db.delete(connection)
    db.commit()
