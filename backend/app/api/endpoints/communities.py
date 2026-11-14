"""Communities are groupings of a water committee's connections (a village, a
distribution line / reading circuit).  They are not part of the account hierarchy."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, MANAGE_ROLES, get_current_user, require_role
from app.db.session import get_db
from app.models.community import Community
from app.models.connection import Connection
from app.models.user import User
from app.models.user_relation import EntityLevel
from app.schemas.community import CommunityCreate, CommunityResponse, CommunityUpdate
from app.services.scope import (
    parent_level,
    require_committee,
    require_community,
    require_manage,
    scope_communities,
)

router = APIRouter(prefix="/communities", tags=["communities"])


def _response(db: Session, community: Community) -> CommunityResponse:
    response = CommunityResponse.model_validate(community)
    response.water_committee_name = (
        community.water_committee.name if community.water_committee else None
    )
    response.connection_count = (
        db.query(Connection).filter(Connection.community_id == community.id).count()
    )
    return response


def _default_committee_id(user: User) -> uuid.UUID | None:
    rel = user.parent
    if rel is not None and parent_level(user) == EntityLevel.WATER_COMMITTEE:
        return rel.water_committee_id
    return None


@router.get("/", response_model=list[CommunityResponse])
def list_communities(
    water_committee_id: uuid.UUID | None = Query(None),
    country: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = scope_communities(db, current_user, db.query(Community))
    if water_committee_id:
        query = query.filter(Community.water_committee_id == water_committee_id)
    if country:
        query = query.filter(Community.country == country)
    return [_response(db, c) for c in query.order_by(Community.name).offset(skip).limit(limit).all()]


@router.post("/", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED)
def create_community(
    payload: CommunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*MANAGE_ROLES)),
):
    """Water committee administrators (and the levels above) add groupings."""
    require_manage(current_user, EntityLevel.WATER_COMMITTEE)
    data = payload.model_dump()
    committee_id = data.get("water_committee_id") or _default_committee_id(current_user)
    if committee_id is None:
        raise HTTPException(status_code=400, detail="Choose the water committee this community belongs to")
    committee = require_committee(db, current_user, committee_id)
    data["water_committee_id"] = committee.id
    community = Community(**data)
    db.add(community)
    db.commit()
    db.refresh(community)
    return _response(db, community)


@router.get("/{community_id}", response_model=CommunityResponse)
def get_community(
    community_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _response(db, require_community(db, current_user, community_id))


@router.patch("/{community_id}", response_model=CommunityResponse)
def update_community(
    community_id: uuid.UUID,
    payload: CommunityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    community = require_community(db, current_user, community_id)
    data = payload.model_dump(exclude_unset=True)
    if "water_committee_id" in data and not data["water_committee_id"]:
        raise HTTPException(status_code=400, detail="A community must belong to a water committee")
    if data.get("water_committee_id"):
        require_committee(db, current_user, data["water_committee_id"])
    for field, value in data.items():
        setattr(community, field, value)
    db.commit()
    db.refresh(community)
    return _response(db, community)


@router.delete("/{community_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_community(
    community_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*MANAGE_ROLES)),
):
    require_manage(current_user, EntityLevel.WATER_COMMITTEE)
    community = require_community(db, current_user, community_id)
    # Connections keep existing under the committee; they just lose the grouping.
    db.query(Connection).filter(Connection.community_id == community_id).update(
        {Connection.community_id: None}, synchronize_session=False
    )
    db.delete(community)
    db.commit()
