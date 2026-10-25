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
    if _partner_wide(user):
        if not user.partner_id:
            return []
        rows = db.query(WaterCommittee.id).filter(WaterCommittee.partner_id == user.partner_id)
        return [r[0] for r in rows]
    if user.water_committee_id:
        return [user.water_committee_id]
    community_id = user.community_id or _household_community_id(db, user)
    if community_id:
        community = db.query(Community).filter(Community.id == community_id).first()
        if community and community.water_committee_id:
            return [community.water_committee_id]
    return []


def _partner_wide(user: User) -> bool:
    """Partner administrators, and viewers attached only to a partner, see the whole partner."""
    if user.role == UserRole.PARTNER_ADMIN:
        return True
    return (
        user.role == UserRole.READER
        and user.partner_id is not None
        and user.water_committee_id is None
        and user.community_id is None
        and user.household_id is None
    )


def _household_community_id(db: Session, user: User) -> uuid.UUID | None:
    if not user.household_id:
        return None
    row = db.query(Household.community_id).filter(Household.id == user.household_id).first()
    return row[0] if row else None


def visible_household_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Households this user may see, or None for "every household in the visible communities"."""
    if user.role == UserRole.READER and user.household_id:
        return [user.household_id]
    return None


def visible_community_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Communities this user may see, or None for no restriction."""
    if user.role == UserRole.SUPER_ADMIN:
        return None
    if _partner_wide(user):
        if not user.partner_id:
            return []
        rows = db.query(Community.id).filter(Community.partner_id == user.partner_id)
        return [r[0] for r in rows]
    ids: set[uuid.UUID] = set()
    if user.role == UserRole.READER and user.household_id:
        community_id = _household_community_id(db, user)
        return [community_id] if community_id else []
    if user.role in (UserRole.OPERATOR, UserRole.READER) and user.assigned_communities:
        ids.update(c.id for c in user.assigned_communities)
        if user.community_id:
            ids.add(user.community_id)
        return list(ids)
    if user.water_committee_id:
        rows = db.query(Community.id).filter(
            Community.water_committee_id == user.water_committee_id
        )
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
    household_ids = visible_household_ids(db, user)
    if household_ids is not None:
        return query.filter(Household.id.in_(household_ids))
    ids = visible_community_ids(db, user)
    if ids is None:
        return query
    return query.filter(Household.community_id.in_(ids)) if ids else query.filter(False)


def can_see_household(db: Session, user: User, household: Household) -> bool:
    household_ids = visible_household_ids(db, user)
    if household_ids is not None:
        return household.id in household_ids
    return can_see_community(db, user, household.community_id)


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
    if not can_see_household(db, user, household):
        raise forbid()
    return household


def require_committee(db: Session, user: User, committee_id: uuid.UUID) -> WaterCommittee:
    committee = db.query(WaterCommittee).filter(WaterCommittee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Water committee not found"
        )
    if not can_see_committee(db, user, committee_id):
        raise forbid()
    return committee
