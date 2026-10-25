"""The whole hierarchy as one scoped tree.

ORG -> PARTNER -> COMMITTEE -> COMMUNITY -> HOUSEHOLD -> METER. Each login gets the
branch below its own level, built on the server so every client sees the same scope.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.community import Community
from app.models.household import Household
from app.models.meter import Meter
from app.models.organization import Organization
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.models.water_committee import WaterCommittee
from app.services.scope import scope_committees, scope_communities, scope_households

router = APIRouter(prefix="/structure", tags=["structure"])


class TreeNode(BaseModel):
    level: str  # organization | partner | committee | community | household | meter
    id: str
    name: str
    meta: str | None = None
    status: str | None = None
    children: list["TreeNode"] = []


class TreeResponse(BaseModel):
    root_level: str
    nodes: list[TreeNode]


def _meter_node(m: Meter) -> TreeNode:
    status = m.status.value if hasattr(m.status, "value") else str(m.status)
    meta = f"last reading {m.last_reading_value:g} m³" if status == "active" else status
    return TreeNode(level="meter", id=str(m.id), name=m.serial_number, meta=meta, status=status)


@router.get("/tree", response_model=TreeResponse)
def structure_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    committees = scope_committees(db, current_user, db.query(WaterCommittee)).order_by(WaterCommittee.name).all()
    communities = scope_communities(db, current_user, db.query(Community)).order_by(Community.name).all()
    households = scope_households(db, current_user, db.query(Household)).order_by(Household.head_of_household).all()
    household_ids = [h.id for h in households]
    meters = (
        db.query(Meter).filter(Meter.household_id.in_(household_ids)).order_by(Meter.created_at.desc()).all()
        if household_ids else []
    )

    meters_by_household: dict = {}
    for m in meters:
        meters_by_household.setdefault(m.household_id, []).append(_meter_node(m))
    households_by_community: dict = {}
    for h in households:
        status = h.status.value if hasattr(h.status, "value") else str(h.status)
        households_by_community.setdefault(h.community_id, []).append(
            TreeNode(level="household", id=str(h.id), name=h.head_of_household, meta=h.account_number,
                     status=status, children=meters_by_household.get(h.id, []))
        )
    communities_by_committee: dict = {}
    for c in communities:
        communities_by_committee.setdefault(c.water_committee_id, []).append(
            TreeNode(level="community", id=str(c.id), name=c.name, meta=c.region,
                     children=households_by_community.get(c.id, []))
        )
    committees_by_partner: dict = {}
    for w in committees:
        committees_by_partner.setdefault(w.partner_id, []).append(
            TreeNode(level="committee", id=str(w.id), name=w.name, meta=w.region,
                     children=communities_by_committee.get(w.id, []))
        )

    # Viewers attached to one household or one community start there.
    if current_user.role == UserRole.READER and current_user.household_id:
        nodes = [n for group in households_by_community.values() for n in group]
        return TreeResponse(root_level="household", nodes=nodes)
    if current_user.role in (UserRole.READER, UserRole.OPERATOR) and not current_user.water_committee_id and (
        current_user.community_id or current_user.assigned_communities
    ):
        nodes = [n for group in communities_by_committee.values() for n in group]
        return TreeResponse(root_level="community", nodes=nodes)
    if current_user.water_committee_id:
        return TreeResponse(root_level="committee", nodes=committees_by_partner.get(current_user.partner_id, [])
                            if current_user.partner_id else [n for g in committees_by_partner.values() for n in g])
    if current_user.role != UserRole.SUPER_ADMIN:
        return TreeResponse(root_level="partner", nodes=[n for g in committees_by_partner.values() for n in g])

    partners = db.query(Partner).order_by(Partner.name).all()
    partners_by_org: dict = {}
    for p in partners:
        partners_by_org.setdefault(p.organization_id, []).append(
            TreeNode(level="partner", id=str(p.id), name=p.name, meta=p.country,
                     children=committees_by_partner.get(p.id, []))
        )
    orgs = db.query(Organization).order_by(Organization.name).all()
    nodes = [
        TreeNode(level="organization", id=str(o.id), name=o.name, meta=o.country,
                 children=partners_by_org.get(o.id, []))
        for o in orgs
    ]
    nodes.extend(partners_by_org.get(None, []))
    return TreeResponse(root_level="organization", nodes=nodes)
