import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, READING_ROLES, get_current_user, require_role
from app.db.session import get_db
from app.models.connection import Connection, ConnectionStatus
from app.models.meter import Meter, MeterReading, MeterStatus
from app.models.community import Community
from app.models.user import User
from app.services.scope import require_connection, scope_connections
from app.schemas.meter import (
    MeterCreate,
    MeterReadingCreate,
    MeterReadingResponse,
    MeterResponse,
    ReadingContext,
)
from app.services.readings import expected_consumption, record_reading

router = APIRouter(prefix="/meters", tags=["meters"])


@router.get("/", response_model=list[MeterResponse])
def list_meters(
    connection_id: uuid.UUID | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Meter).join(Connection, Connection.id == Meter.connection_id)
    query = scope_connections(db, current_user, query)
    if connection_id:
        query = query.filter(Meter.connection_id == connection_id)
    return query.order_by(Meter.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/reading-context", response_model=list[ReadingContext])
def reading_context(
    community_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Everything the field app needs to read meters, cacheable for offline use."""
    query = (
        db.query(Connection, Meter, Community)
        .join(Meter, Meter.connection_id == Connection.id)
        .outerjoin(Community, Community.id == Connection.community_id)
        .filter(Connection.status == ConnectionStatus.ACTIVE)
        .filter(Meter.status == MeterStatus.ACTIVE)
    )
    query = scope_connections(db, current_user, query)
    if community_id:
        query = query.filter(Connection.community_id == community_id)

    rows = query.order_by(Community.name, Connection.account_number).all()
    now = datetime.now(timezone.utc)
    results = []
    for connection, meter, community in rows:
        daily, days, expected = expected_consumption(db, meter, now)
        results.append(
            ReadingContext(
                connection_id=connection.id,
                account_number=connection.account_number,
                contact_name=connection.contact_name,
                address=connection.address,
                community_id=connection.community_id,
                community_name=community.name,
                meter_id=meter.id,
                serial_number=meter.serial_number,
                last_reading_value=meter.last_reading_value,
                last_reading_date=meter.last_reading_date,
                avg_consumption_m3=meter.avg_consumption_m3,
                avg_daily_consumption_m3=daily,
                days_since_last_reading=days,
                expected_consumption_m3=expected,
                expected_reading_value=(
                    round(meter.last_reading_value + expected, 1) if expected is not None else None
                ),
            )
        )
    return results


@router.post("/", response_model=MeterResponse, status_code=status.HTTP_201_CREATED)
def create_meter(
    payload: MeterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*READING_ROLES)),
):
    """Fit a meter. If the connection already has an active one it is retired (replaced/removed)
    and the new meter becomes the one operators read; old readings stay on the old meter."""
    connection = require_connection(db, current_user, payload.connection_id)
    if db.query(Meter).filter(Meter.serial_number == payload.serial_number).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Meter {payload.serial_number} is already registered",
        )
    active = [m for m in connection.meters if m.status == MeterStatus.ACTIVE]
    if active:
        retire_as = payload.retire_existing_as or MeterStatus.REPLACED
        if retire_as == MeterStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Choose replaced, removed or faulty for the old meter")
        for old in active:
            if payload.final_reading_of_old_meter is not None and (
                payload.final_reading_of_old_meter >= old.last_reading_value
            ):
                record_reading(
                    db,
                    old,
                    reading_value=payload.final_reading_of_old_meter,
                    reading_date=payload.install_date or datetime.now(timezone.utc),
                    notes="Final reading before meter was taken out",
                    recorded_by=current_user.full_name,
                )
            old.status = retire_as
    data = payload.model_dump(exclude={"initial_reading", "retire_existing_as", "final_reading_of_old_meter"})
    meter = Meter(**data, last_reading_value=payload.initial_reading, status=MeterStatus.ACTIVE)
    if meter.install_date is None:
        meter.install_date = datetime.now(timezone.utc)
    db.add(meter)
    connection.has_meter = True
    db.commit()
    db.refresh(meter)
    return meter


@router.patch("/{meter_id}/status", response_model=MeterResponse)
def set_meter_status(
    meter_id: uuid.UUID,
    new_status: MeterStatus = Query(..., alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Mark a meter faulty/removed, or make a retired meter the active one again."""
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if not meter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    connection = require_connection(db, current_user, meter.connection_id)
    if new_status == MeterStatus.ACTIVE:
        for other in connection.meters:
            if other.id != meter.id and other.status == MeterStatus.ACTIVE:
                other.status = MeterStatus.REPLACED
    meter.status = new_status
    connection.has_meter = any(m.status == MeterStatus.ACTIVE for m in connection.meters)
    db.commit()
    db.refresh(meter)
    return meter


@router.post("/readings", response_model=MeterReadingResponse, status_code=status.HTTP_201_CREATED)
def create_reading(
    payload: MeterReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*READING_ROLES)),
):
    meter = db.query(Meter).filter(Meter.id == payload.meter_id).first()
    if not meter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    require_connection(db, current_user, meter.connection_id)
    if meter.status != MeterStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Meter {meter.serial_number} is {meter.status.value}; read the connection's active meter",
        )

    reading = record_reading(
        db,
        meter,
        reading_value=payload.reading_value,
        reading_date=payload.reading_date,
        notes=payload.notes,
        is_estimated=payload.is_estimated,
        recorded_by=payload.recorded_by or current_user.full_name,
        photo_url=payload.photo_url,
    )
    db.commit()
    db.refresh(reading)
    return reading


@router.get("/readings", response_model=list[MeterReadingResponse])
def list_readings(
    meter_id: uuid.UUID | None = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(MeterReading)
        .join(Meter, Meter.id == MeterReading.meter_id)
        .join(Connection, Connection.id == Meter.connection_id)
    )
    query = scope_connections(db, current_user, query)
    if meter_id:
        query = query.filter(MeterReading.meter_id == meter_id)
    return query.order_by(MeterReading.reading_date.desc()).offset(skip).limit(limit).all()


@router.delete("/readings/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Remove a mis-entered reading and roll the meter back to the previous one."""
    reading = db.query(MeterReading).filter(MeterReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading not found")
    if reading.invoice_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This reading is on a bill. Delete the bill first.",
        )
    meter_id = reading.meter_id
    owner = db.query(Meter).filter(Meter.id == meter_id).first()
    if owner:
        require_connection(db, current_user, owner.connection_id)
    db.delete(reading)
    db.flush()
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if meter:
        latest = (
            db.query(MeterReading)
            .filter(MeterReading.meter_id == meter_id)
            .order_by(MeterReading.reading_date.desc())
            .first()
        )
        meter.last_reading_value = latest.reading_value if latest else 0.0
        meter.last_reading_date = latest.reading_date if latest else None
    db.commit()
