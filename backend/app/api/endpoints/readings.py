"""Raw meter readings across the hierarchy, and bulk household import."""

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, get_current_user, require_role
from app.db.session import get_db
from app.models.billing import Invoice
from app.models.community import Community
from app.models.household import Household
from app.models.meter import Meter, MeterReading, MeterStatus
from app.models.user import User
from app.services.scope import require_community, visible_community_ids, visible_household_ids

router = APIRouter(prefix="/readings", tags=["readings"])


class RawReading(BaseModel):
    id: uuid.UUID
    reading_date: datetime
    reading_value: float
    previous_value: float
    consumption_m3: float
    flag_reason: str | None
    is_estimated: bool
    recorded_by: str | None
    notes: str | None
    meter_id: uuid.UUID
    serial_number: str
    household_id: uuid.UUID
    account_number: str
    head_of_household: str
    community_id: uuid.UUID
    community_name: str
    water_committee_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    invoice_number: str | None


@router.get("/", response_model=list[RawReading])
def list_raw_readings(
    water_committee_id: uuid.UUID | None = Query(None),
    community_id: uuid.UUID | None = Query(None),
    household_id: uuid.UUID | None = Query(None),
    meter_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    flagged_only: bool = Query(False),
    unbilled_only: bool = Query(False),
    skip: int = 0,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every reading the current login is allowed to see, newest first."""
    query = (
        db.query(MeterReading, Meter, Household, Community, Invoice)
        .join(Meter, Meter.id == MeterReading.meter_id)
        .join(Household, Household.id == Meter.household_id)
        .join(Community, Community.id == Household.community_id)
        .outerjoin(Invoice, Invoice.id == MeterReading.invoice_id)
    )
    ids = visible_community_ids(db, current_user)
    if ids is not None:
        query = query.filter(Household.community_id.in_(ids)) if ids else query.filter(False)
    household_ids = visible_household_ids(db, current_user)
    if household_ids is not None:
        query = query.filter(Household.id.in_(household_ids))
    if water_committee_id:
        query = query.filter(Community.water_committee_id == water_committee_id)
    if community_id:
        query = query.filter(Household.community_id == community_id)
    if household_id:
        query = query.filter(Household.id == household_id)
    if meter_id:
        query = query.filter(MeterReading.meter_id == meter_id)
    if date_from:
        query = query.filter(MeterReading.reading_date >= date_from)
    if date_to:
        query = query.filter(MeterReading.reading_date <= date_to)
    if flagged_only:
        query = query.filter(MeterReading.flag_reason.isnot(None))
    if unbilled_only:
        query = query.filter(MeterReading.invoice_id.is_(None))
    rows = (
        query.order_by(MeterReading.reading_date.desc(), Household.account_number)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        RawReading(
            id=r.id,
            reading_date=r.reading_date,
            reading_value=r.reading_value,
            previous_value=r.previous_value,
            consumption_m3=r.consumption_m3,
            flag_reason=r.flag_reason,
            is_estimated=r.is_estimated,
            recorded_by=r.recorded_by,
            notes=r.notes,
            meter_id=m.id,
            serial_number=m.serial_number,
            household_id=h.id,
            account_number=h.account_number,
            head_of_household=h.head_of_household,
            community_id=c.id,
            community_name=c.name,
            water_committee_id=c.water_committee_id,
            invoice_id=inv.id if inv else None,
            invoice_number=inv.invoice_number if inv else None,
        )
        for r, m, h, c, inv in rows
    ]


REQUIRED_COLUMNS = ("account_number", "head_of_household")
OPTIONAL_COLUMNS = (
    "address",
    "phone",
    "members_count",
    "meter_serial_number",
    "meter_brand",
    "meter_initial_reading",
    "notes",
)


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportResult(BaseModel):
    created_households: int
    created_meters: int
    errors: list[ImportRowError]


@router.get("/import/template")
def import_template(current_user: User = Depends(require_role(*ADMIN_ROLES))):
    return {
        "required_columns": list(REQUIRED_COLUMNS),
        "optional_columns": list(OPTIONAL_COLUMNS),
        "example": "account_number,head_of_household,address,phone,members_count,"
        "meter_serial_number,meter_brand,meter_initial_reading,notes\n"
        "A-001,Mary Johnson,12 Cedar St,(505) 555-0101,4,MTR-1001,Elster,1250,\n",
    }


@router.post("/import", response_model=ImportResult)
async def import_households(
    community_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Load households (and their meters) for one community from a CSV file.

    The whole file is checked first; nothing is saved if any row has a problem.
    """
    require_community(db, current_user, community_id)
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing column(s): {', '.join(missing)}. "
            f"Required: {', '.join(REQUIRED_COLUMNS)}.",
        )

    errors: list[ImportRowError] = []
    pending: list[tuple[Household, Meter | None]] = []
    seen_accounts: set[str] = set()
    seen_serials: set[str] = set()
    existing_accounts = {a for (a,) in db.query(Household.account_number).all()}
    existing_serials = {s for (s,) in db.query(Meter.serial_number).all()}

    for index, row in enumerate(reader, start=2):
        data = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        account = data.get("account_number", "")
        name = data.get("head_of_household", "")
        if not account or not name:
            errors.append(
                ImportRowError(
                    row=index, message="account_number and head_of_household are required"
                )
            )
            continue
        if account in existing_accounts or account in seen_accounts:
            errors.append(ImportRowError(row=index, message=f"Account {account} already exists"))
            continue
        serial = data.get("meter_serial_number", "")
        if serial and (serial in existing_serials or serial in seen_serials):
            errors.append(ImportRowError(row=index, message=f"Meter {serial} already registered"))
            continue
        try:
            members = int(data.get("members_count") or 1)
            initial = float(data.get("meter_initial_reading") or 0)
        except ValueError:
            errors.append(
                ImportRowError(
                    row=index, message="members_count and meter_initial_reading must be numbers"
                )
            )
            continue
        household = Household(
            account_number=account,
            head_of_household=name,
            address=data.get("address") or None,
            phone=data.get("phone") or None,
            members_count=members,
            notes=data.get("notes") or None,
            has_meter=bool(serial),
            community_id=community_id,
        )
        meter = None
        if serial:
            meter = Meter(
                serial_number=serial,
                brand=data.get("meter_brand") or None,
                install_date=datetime.now(timezone.utc),
                last_reading_value=initial,
                status=MeterStatus.ACTIVE,
            )
        seen_accounts.add(account)
        if serial:
            seen_serials.add(serial)
        pending.append((household, meter))

    if errors:
        return ImportResult(created_households=0, created_meters=0, errors=errors)

    meters = 0
    for household, meter in pending:
        db.add(household)
        db.flush()
        if meter:
            meter.household_id = household.id
            db.add(meter)
            meters += 1
    db.commit()
    return ImportResult(created_households=len(pending), created_meters=meters, errors=[])
