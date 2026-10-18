import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.billing import Invoice, Payment
from app.models.community import Community
from app.models.expense import Expense
from app.models.household import Household
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.models.water_committee import WaterCommittee
from app.schemas.water_committee import (
    CommitteeFinancials,
    WaterCommitteeCreate,
    WaterCommitteeResponse,
    WaterCommitteeUpdate,
)
from app.services.scope import forbid, require_committee, scope_committees

router = APIRouter(prefix="/water-committees", tags=["water-committees"])


def _response(db: Session, committee: WaterCommittee) -> WaterCommitteeResponse:
    response = WaterCommitteeResponse.model_validate(committee)
    response.partner_name = committee.partner.name if committee.partner else None
    response.community_count = (
        db.query(Community).filter(Community.water_committee_id == committee.id).count()
    )
    response.household_count = (
        db.query(Household)
        .join(Community, Community.id == Household.community_id)
        .filter(Community.water_committee_id == committee.id)
        .count()
    )
    return response


@router.get("/", response_model=list[WaterCommitteeResponse])
def list_committees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = scope_committees(db, current_user, db.query(WaterCommittee))
    return [_response(db, c) for c in query.order_by(WaterCommittee.name).all()]


@router.post("/", response_model=WaterCommitteeResponse, status_code=status.HTTP_201_CREATED)
def create_committee(
    payload: WaterCommitteeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.PARTNER_ADMIN)),
):
    """Partners set up the committees they support."""
    partner_id = payload.partner_id
    if current_user.role == UserRole.PARTNER_ADMIN:
        partner_id = current_user.partner_id
    if partner_id is None:
        partner = db.query(Partner).order_by(Partner.created_at).first()
        if not partner:
            raise HTTPException(status_code=400, detail="Create a partner organisation first")
        partner_id = partner.id
    committee = WaterCommittee(**payload.model_dump(exclude={"partner_id"}), partner_id=partner_id)
    db.add(committee)
    db.commit()
    db.refresh(committee)
    return _response(db, committee)


@router.get("/{committee_id}", response_model=WaterCommitteeResponse)
def get_committee(
    committee_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _response(db, require_committee(db, current_user, committee_id))


@router.patch("/{committee_id}", response_model=WaterCommitteeResponse)
def update_committee(
    committee_id: uuid.UUID,
    payload: WaterCommitteeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.SUPER_ADMIN, UserRole.PARTNER_ADMIN, UserRole.COMMUNITY_ADMIN)
    ),
):
    committee = require_committee(db, current_user, committee_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(committee, field, value)
    db.commit()
    db.refresh(committee)
    return _response(db, committee)


@router.delete("/{committee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_committee(
    committee_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.PARTNER_ADMIN)),
):
    committee = require_committee(db, current_user, committee_id)
    if db.query(Community).filter(Community.water_committee_id == committee_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Move or delete this committee's communities first",
        )
    db.query(User).filter(User.water_committee_id == committee_id).update(
        {User.water_committee_id: None}, synchronize_session=False
    )
    db.delete(committee)
    db.commit()


@router.get("/{committee_id}/financials", response_model=CommitteeFinancials)
def committee_financials(
    committee_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Money across every community the committee runs, in one view."""
    if current_user.role in (UserRole.OPERATOR, UserRole.READER):
        raise forbid()
    require_committee(db, current_user, committee_id)
    communities = (
        db.query(Community).filter(Community.water_committee_id == committee_id).all()
    )
    rows = []
    totals = {"billed": 0.0, "collected": 0.0, "outstanding": 0.0, "expenses": 0.0}
    currency = communities[0].currency if communities else "USD"
    for community in communities:
        hh = db.query(Household.id).filter(Household.community_id == community.id).subquery()
        billed = db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0)).filter(
            Invoice.household_id.in_(hh)
        ).scalar()
        outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0.0)).filter(
            Invoice.household_id.in_(hh)
        ).scalar()
        collected = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
            Payment.household_id.in_(hh)
        ).scalar()
        expenses = db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(
            Expense.community_id == community.id
        ).scalar()
        row = {
            "community_id": str(community.id),
            "community_name": community.name,
            "total_billed": round(float(billed), 2),
            "total_collected": round(float(collected), 2),
            "outstanding": round(float(outstanding), 2),
            "total_expenses": round(float(expenses), 2),
        }
        rows.append(row)
        totals["billed"] += row["total_billed"]
        totals["collected"] += row["total_collected"]
        totals["outstanding"] += row["outstanding"]
        totals["expenses"] += row["total_expenses"]
    return CommitteeFinancials(
        water_committee_id=committee_id,
        currency=currency,
        total_billed=round(totals["billed"], 2),
        total_collected=round(totals["collected"], 2),
        outstanding=round(totals["outstanding"], 2),
        total_expenses=round(totals["expenses"], 2),
        net_position=round(totals["collected"] - totals["expenses"], 2),
        communities=rows,
    )
