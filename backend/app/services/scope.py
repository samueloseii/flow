"""Who may see and create what.

Hierarchy: organisation (sys admin) > partner > water committee > community > household > meter.
A login is attached to one level and sees only the branch below it.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from app.models.community import Community
from app.models.household import Household
from app.models.user import User, UserRole
from app.models.water_committee import WaterCommittee

# Lower number = more authority. Accounts may only create roles at their rank or below.
ROLE_RANK = {
    UserRole.SUPER_ADMIN: 0,
    UserRole.PARTNER_ADMIN: 1,
    UserRole.COMMUNITY_ADMIN: 2,  # water committee administrator
    UserRole.TREASURER: 3,
    UserRole.OPERATOR: 4,
    UserRole.READER: 5,  # view-only / community member
}

ROLE_LABELS = {
    UserRole.SUPER_ADMIN: "System administrator",
    UserRole.PARTNER_ADMIN: "Partner administrator",
    UserRole.COMMUNITY_ADMIN: "Water committee administrator",
    UserRole.TREASURER: "Treasurer",
    UserRole.OPERATOR: "Operator",
    UserRole.READER: "Viewer",
}


def can_create_role(creator: User, role: UserRole) -> bool:
    return ROLE_RANK[role] >= ROLE_RANK[creator.role]


def forbid(detail: str = "Outside your area of responsibility") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def visible_committee_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Committees this user may see, or None for no restriction (sys admin)."""
    if user.role == UserRole.SUPER_ADMIN:
        return None
    if user.role == UserRole.PARTNER_ADMIN:
        if not user.partner_id:
            return []
        rows = db.query(WaterCommittee.id).filter(WaterCommittee.partner_id == user.partner_id)
        return [r[0] for r in rows]
    if user.water_committee_id:
        return [user.water_committee_id]
    if user.community_id:
        community = db.query(Community).filter(Community.id == user.community_id).first()
        if community and community.water_committee_id:
            return [community.water_committee_id]
    return []


def visible_community_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Communities this user may see, or None for no restriction."""
    if user.role == UserRole.SUPER_ADMIN:
        return None
    if user.role == UserRole.PARTNER_ADMIN:
        if not user.partner_id:
            return []
        rows = db.query(Community.id).filter(Community.partner_id == user.partner_id)
        return [r[0] for r in rows]
    ids: set[uuid.UUID] = set()
    if user.role in (UserRole.OPERATOR, UserRole.READER) and user.assigned_communities:
        ids.update(c.id for c in user.assigned_communities)
        if user.community_id:
            ids.add(user.community_id)
        return list(ids)
    if user.water_committee_id:
        rows = db.query(Community.id).filter(Community.water_committee_id == user.water_committee_id)
        ids.update(r[0] for r in rows)
    if user.community_id:
        ids.add(user.community_id)
    return list(ids)


def scope_communities(db: Session, user: User, query: Query) -> Query:
    ids = visible_community_ids(db, user)
    if ids is None:
        return query
    return query.filter(Community.id.in_(ids)) if ids else query.filter(False)


def scope_households(db: Session, user: User, query: Query) -> Query:
    ids = visible_community_ids(db, user)
    if ids is None:
        return query
    return query.filter(Household.community_id.in_(ids)) if ids else query.filter(False)


def scope_committees(db: Session, user: User, query: Query) -> Query:
    ids = visible_committee_ids(db, user)
    if ids is None:
        return query
    return query.filter(WaterCommittee.id.in_(ids)) if ids else query.filter(False)


def can_see_community(db: Session, user: User, community_id: uuid.UUID) -> bool:
    ids = visible_community_ids(db, user)
    return ids is None or community_id in ids


def can_see_committee(db: Session, user: User, committee_id: uuid.UUID) -> bool:
    ids = visible_committee_ids(db, user)
    return ids is None or committee_id in ids


def require_community(db: Session, user: User, community_id: uuid.UUID) -> Community:
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    if not can_see_community(db, user, community_id):
        raise forbid()
    return community


def require_household(db: Session, user: User, household_id: uuid.UUID) -> Household:
    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    if not can_see_community(db, user, household.community_id):
        raise forbid()
    return household


def require_committee(db: Session, user: User, committee_id: uuid.UUID) -> WaterCommittee:
    committee = db.query(WaterCommittee).filter(WaterCommittee.id == committee_id).first()
    if not committee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Water committee not found")
    if not can_see_committee(db, user, committee_id):
        raise forbid()
    return committee
