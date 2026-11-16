import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, READING_ROLES, get_current_user, require_role
from app.db.session import get_db
from app.models.community import Community
from app.services.scope import require_committee, visible_committee_ids
from app.models.maintenance import MaintenanceRecord, MaintenanceStatus
from app.models.user import User
from app.schemas.maintenance import MaintenanceCreate, MaintenanceResponse, MaintenanceUpdate

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _response(record: MaintenanceRecord, community: Community | None) -> MaintenanceResponse:
    response = MaintenanceResponse.model_validate(record)
    if community:
        response.community_name = community.name
    return response


def _resolve_committee(db: Session, user: User, water_committee_id, community_id):
    """Expenses and maintenance belong to the water committee; a community is an optional grouping."""
    community = db.query(Community).filter(Community.id == community_id).first() if community_id else None
    if community_id and not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    committee_id = water_committee_id or (community.water_committee_id if community else None)
    if committee_id is None:
        rel = user.parent
        if rel is not None and rel.water_committee_id:
            committee_id = rel.water_committee_id
    if committee_id is None:
        raise HTTPException(status_code=400, detail="Choose the water committee")
    if community and community.water_committee_id != committee_id:
        raise HTTPException(status_code=400, detail="That community belongs to a different water committee")
    require_committee(db, user, committee_id)
    return committee_id, community


@router.get("/", response_model=list[MaintenanceResponse])
def list_maintenance(
    water_committee_id: uuid.UUID | None = Query(None),
    community_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = Query(None),
    open_only: bool = Query(False),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MaintenanceRecord, Community).outerjoin(
        Community, Community.id == MaintenanceRecord.community_id
    )
    visible = visible_committee_ids(db, current_user)
    if visible is not None:
        query = query.filter(MaintenanceRecord.water_committee_id.in_(visible))
    if water_committee_id:
        query = query.filter(MaintenanceRecord.water_committee_id == water_committee_id)
    if community_id:
        query = query.filter(MaintenanceRecord.community_id == community_id)
    if status_filter:
        query = query.filter(MaintenanceRecord.status == status_filter)
    if open_only:
        query = query.filter(
            MaintenanceRecord.status.in_(
                (MaintenanceStatus.REPORTED, MaintenanceStatus.IN_PROGRESS)
            )
        )
    if priority:
        query = query.filter(MaintenanceRecord.priority == priority)
    rows = (
        query.order_by(MaintenanceRecord.reported_date.desc()).offset(skip).limit(limit).all()
    )
    return [_response(record, community) for record, community in rows]


@router.post("/", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED)
def create_maintenance(
    payload: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*READING_ROLES)),
):
    committee_id, _community = _resolve_committee(db, current_user, payload.water_committee_id, payload.community_id)
    data = payload.model_dump()
    data["water_committee_id"] = committee_id
    record = MaintenanceRecord(**data)
    if not record.reported_by:
        record.reported_by = current_user.full_name
    db.add(record)
    db.commit()
    db.refresh(record)
    return _response(record, record.community)


@router.get("/{record_id}", response_model=MaintenanceResponse)
def get_maintenance(
    record_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return _response(record, record.community)


@router.patch("/{record_id}", response_model=MaintenanceResponse)
def update_maintenance(
    record_id: uuid.UUID,
    payload: MaintenanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Triage is the administrator's job: priority, status and resolution."""
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(record, field, value)
    if updates.get("status") == MaintenanceStatus.COMPLETED:
        record.resolved_date = record.resolved_date or datetime.now(timezone.utc)
        record.resolved_by = record.resolved_by or current_user.full_name
    db.commit()
    db.refresh(record)
    return _response(record, record.community)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_maintenance(
    record_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    db.delete(record)
    db.commit()
