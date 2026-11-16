import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.billing import Invoice, Payment
from app.models.community import Community
from app.models.expense import Expense
from app.models.connection import Connection
from app.models.partner import Partner
from app.models.tariff import Tariff
from app.models.user import User, UserRole
from app.models.water_committee import WaterCommittee
from app.schemas.water_committee import (
    CommitteeFinancials,
    WaterCommitteeCreate,
    WaterCommitteeResponse,
    WaterCommitteeUpdate,
)
from app.models.user_relation import EntityLevel
from app.services.scope import forbid, require_committee, require_manage, require_partner, scope_committees, visible_partner_ids

router = APIRouter(prefix="/water-committees", tags=["water-committees"])


def _response(db: Session, committee: WaterCommittee) -> WaterCommitteeResponse:
    response = WaterCommitteeResponse.model_validate(committee)
    response.partner_name = committee.partner.name if committee.partner else None
    response.community_count = (
        db.query(Community).filter(Community.water_committee_id == committee.id).count()
    )
    response.connection_count = (
        db.query(Connection).filter(Connection.water_committee_id == committee.id).count()
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
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Partner administrators (and above) set up the committees they support."""
    require_manage(current_user, EntityLevel.WATER_COMMITTEE)
    partner_id = payload.partner_id
    if partner_id is None:
        visible = visible_partner_ids(db, current_user)
        if visible is None:
            partner = db.query(Partner).order_by(Partner.created_at).first()
            if not partner:
                raise HTTPException(status_code=400, detail="Create a partner first")
            partner_id = partner.id
        elif len(visible) == 1:
            partner_id = visible[0]
        else:
            raise HTTPException(status_code=400, detail="Choose the partner this committee belongs to")
    require_partner(db, current_user, partner_id)
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
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.EDITOR)),
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
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    require_manage(current_user, EntityLevel.WATER_COMMITTEE)
    committee = require_committee(db, current_user, committee_id)
    if db.query(Connection).filter(Connection.water_committee_id == committee_id).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Move or delete this committee's connections first",
        )
    db.query(Community).filter(Community.water_committee_id == committee_id).delete(synchronize_session=False)
    db.delete(committee)
    db.commit()


@router.get("/{committee_id}/financials", response_model=CommitteeFinancials)
def committee_financials(
    committee_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Money across every community the committee runs, in one view."""
    if current_user.role in (UserRole.OPERATOR, UserRole.VIEWER):
        raise forbid()
    require_committee(db, current_user, committee_id)
    communities = (
        db.query(Community).filter(Community.water_committee_id == committee_id).all()
    )
    default_tariff = db.query(Tariff).filter(Tariff.water_committee_id == committee_id).order_by(Tariff.is_default.desc()).first()
    currency = default_tariff.currency if default_tariff else "USD"
    rows = []
    totals = {"billed": 0.0, "collected": 0.0, "outstanding": 0.0, "expenses": 0.0}
    groups = [(c.id, c.name, Connection.community_id == c.id) for c in communities]
    groups.append((None, "Not grouped" if communities else "All connections",
                   Connection.community_id.is_(None) if communities else Connection.water_committee_id == committee_id))
    for group_id, group_name, cond in groups:
        hh = db.query(Connection.id).filter(Connection.water_committee_id == committee_id, cond).subquery()
        billed = db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0)).filter(
            Invoice.connection_id.in_(hh)
        ).scalar()
        outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0.0)).filter(
            Invoice.connection_id.in_(hh)
        ).scalar()
        collected = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
            Payment.connection_id.in_(hh)
        ).scalar()
        expenses = db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(
            Expense.water_committee_id == committee_id,
            Expense.community_id == group_id if group_id else Expense.community_id.is_(None),
        ).scalar()
        row = {
            "community_id": str(group_id) if group_id else None,
            "community_name": group_name,
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
