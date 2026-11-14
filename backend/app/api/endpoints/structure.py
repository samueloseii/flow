"""The whole hierarchy as one scoped tree.

ORGANIZATION -> PARTNER -> WATER COMMITTEE -> CONNECTION -> METER.  Each login gets the
branch below its own parent entity, built on the server so every client sees the same
scope.  A community (grouping) is shown as a label on the connection, not as a level.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.community import Community
from app.models.connection import Connection
from app.models.meter import Meter
from app.models.organization import Organization
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.models.user_relation import EntityLevel
from app.models.water_committee import WaterCommittee
from app.services.scope import (
    parent_level,
    scope_committees,
    scope_connections,
    visible_organization_ids,
    visible_partner_ids,
)

router = APIRouter(prefix="/structure", tags=["structure"])


class TreeNode(BaseModel):
    level: str  # organization | partner | committee | connection | meter
    id: str
    name: str
    meta: str | None = None
    status: str | None = None
    group: str | None = None  # community / circuit label on a connection
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
    connections = scope_connections(db, current_user, db.query(Connection)).order_by(Connection.contact_name).all()
    connection_ids = [c.id for c in connections]
    meters = (
        db.query(Meter).filter(Meter.connection_id.in_(connection_ids)).order_by(Meter.created_at.desc()).all()
        if connection_ids else []
    )
    community_names = {c.id: c.name for c in db.query(Community.id, Community.name).all()}

    meters_by_connection: dict = {}
    for m in meters:
        meters_by_connection.setdefault(m.connection_id, []).append(_meter_node(m))
    connections_by_committee: dict = {}
    for c in connections:
        status = c.status.value if hasattr(c.status, "value") else str(c.status)
        ctype = c.connection_type.value if hasattr(c.connection_type, "value") else str(c.connection_type)
        connections_by_committee.setdefault(c.water_committee_id, []).append(
            TreeNode(level="connection", id=str(c.id), name=c.contact_name,
                     meta=f"{c.account_number} · {ctype.replace('_', ' ')}", status=status,
                     group=community_names.get(c.community_id) if c.community_id else None,
                     children=meters_by_connection.get(c.id, []))
        )
    committees_by_partner: dict = {}
    for w in committees:
        committees_by_partner.setdefault(w.partner_id, []).append(
            TreeNode(level="committee", id=str(w.id), name=w.name, meta=w.region,
                     children=connections_by_committee.get(w.id, []))
        )

    level = parent_level(current_user)
    if current_user.role != UserRole.SUPER_ADMIN and level is None:
        return TreeResponse(root_level="organization", nodes=[])
    if level == EntityLevel.CONNECTION:
        nodes = [n for group in connections_by_committee.values() for n in group]
        return TreeResponse(root_level="connection", nodes=nodes)
    if level == EntityLevel.WATER_COMMITTEE:
        nodes = [n for g in committees_by_partner.values() for n in g]
        return TreeResponse(root_level="committee", nodes=nodes)

    partner_ids = visible_partner_ids(db, current_user)
    partners_q = db.query(Partner)
    if partner_ids is not None:
        partners_q = partners_q.filter(Partner.id.in_(partner_ids)) if partner_ids else partners_q.filter(False)
    partners = partners_q.order_by(Partner.name).all()
    partners_by_org: dict = {}
    for p in partners:
        partners_by_org.setdefault(p.organization_id, []).append(
            TreeNode(level="partner", id=str(p.id), name=p.name, meta=p.country,
                     children=committees_by_partner.get(p.id, []))
        )
    if level == EntityLevel.PARTNER:
        return TreeResponse(root_level="partner", nodes=[n for g in partners_by_org.values() for n in g])

    org_ids = visible_organization_ids(db, current_user)
    orgs_q = db.query(Organization)
    if org_ids is not None:
        orgs_q = orgs_q.filter(Organization.id.in_(org_ids)) if org_ids else orgs_q.filter(False)
    orgs = orgs_q.order_by(Organization.name).all()
    nodes = [
        TreeNode(level="organization", id=str(o.id), name=o.name, meta=o.country,
                 children=partners_by_org.get(o.id, []))
        for o in orgs
    ]
    nodes.extend(partners_by_org.get(None, []))
    return TreeResponse(root_level="organization", nodes=nodes)
