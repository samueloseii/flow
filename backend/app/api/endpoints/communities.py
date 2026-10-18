import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.community import Community
from app.models.household import Household
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.services.scope import require_committee, require_community, scope_communities
from app.schemas.community import CommunityCreate, CommunityResponse, CommunityUpdate

router = APIRouter(prefix="/communities", tags=["communities"])

COMMUNITY_MANAGERS = (UserRole.SUPER_ADMIN, UserRole.PARTNER_ADMIN, UserRole.COMMUNITY_ADMIN)


def _response(community: Community) -> CommunityResponse:
    response = CommunityResponse.model_validate(community)
    response.water_committee_name = (
        community.water_committee.name if community.water_committee else None
    )
    return response


@router.get("/", response_model=list[CommunityResponse])
def list_communities(
    partner_id: uuid.UUID | None = Query(None),
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
    if partner_id:
        query = query.filter(Community.partner_id == partner_id)
    if country:
        query = query.filter(Community.country == country)
    return [_response(c) for c in query.order_by(Community.name).offset(skip).limit(limit).all()]


@router.post("/", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED)
def create_community(
    payload: CommunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*COMMUNITY_MANAGERS)),
):
    """Water committee administrators (and the levels above) add communities."""
    data = payload.model_dump()
    committee_id = data.get("water_committee_id") or current_user.water_committee_id
    if committee_id is None and current_user.role == UserRole.COMMUNITY_ADMIN:
        raise HTTPException(status_code=400, detail="Choose the water committee this community belongs to")
    committee = require_committee(db, current_user, committee_id) if committee_id else None
    partner_id = committee.partner_id if committee else (data.get("partner_id") or current_user.partner_id)
    if partner_id is None:
        partner = db.query(Partner).order_by(Partner.created_at).first()
        if not partner:
            raise HTTPException(status_code=400, detail="Create a partner organisation first")
        partner_id = partner.id
    data["partner_id"] = partner_id
    data["water_committee_id"] = committee.id if committee else None
    community = Community(**data)
    db.add(community)
    db.commit()
    db.refresh(community)
    return _response(community)


@router.get("/{community_id}", response_model=CommunityResponse)
def get_community(
    community_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _response(require_community(db, current_user, community_id))


@router.patch("/{community_id}", response_model=CommunityResponse)
def update_community(
    community_id: uuid.UUID,
    payload: CommunityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*COMMUNITY_MANAGERS)),
):
    community = require_community(db, current_user, community_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("water_committee_id"):
        committee = require_committee(db, current_user, data["water_committee_id"])
        community.partner_id = committee.partner_id
    for field, value in data.items():
        setattr(community, field, value)
    db.commit()
    db.refresh(community)
    return _response(community)


@router.delete("/{community_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_community(
    community_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*COMMUNITY_MANAGERS)),
):
    community = require_community(db, current_user, community_id)
    if db.query(Household).filter(Household.community_id == community_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete the households in this community first",
        )
    db.query(User).filter(User.community_id == community_id).update(
        {User.community_id: None}, synchronize_session=False
    )
    db.delete(community)
    db.commit()
