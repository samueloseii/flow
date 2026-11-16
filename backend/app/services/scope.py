"""Who may see and change what.

Hierarchy: organization > partner > water committee > connection > meter.
Every account except the super admin has one PARENT relation (the entity it belongs to).
With access_all_children it sees the whole branch below; otherwise its CHILD relations
(communities or connections of that committee) say which parts it may see.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from app.models.community import Community
from app.models.connection import Connection
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.models.user_relation import EntityLevel, RelationType, UserRelation
from app.models.water_committee import WaterCommittee

# Lower number = more authority. Accounts may only create roles at their rank or below.
ROLE_RANK = {
    UserRole.SUPER_ADMIN: 0,
    UserRole.ADMIN: 1,
    UserRole.EDITOR: 2,
    UserRole.OPERATOR: 3,
    UserRole.VIEWER: 4,
}

ROLE_LABELS = {
    UserRole.SUPER_ADMIN: "System administrator",
    UserRole.ADMIN: "Administrator",
    UserRole.EDITOR: "Editor (treasurer)",
    UserRole.OPERATOR: "Operator",
    UserRole.VIEWER: "Viewer",
}

LEVEL_ORDER = [
    EntityLevel.ORGANIZATION,
    EntityLevel.PARTNER,
    EntityLevel.WATER_COMMITTEE,
    EntityLevel.CONNECTION,
]

# Which roles make sense at which parent level (Code Notes / Dan's model).
ROLES_AT_LEVEL = {
    EntityLevel.ORGANIZATION: (UserRole.ADMIN, UserRole.EDITOR, UserRole.VIEWER),
    EntityLevel.PARTNER: (UserRole.ADMIN, UserRole.EDITOR, UserRole.VIEWER),
    EntityLevel.WATER_COMMITTEE: (
        UserRole.ADMIN,
        UserRole.EDITOR,
        UserRole.OPERATOR,
        UserRole.VIEWER,
    ),
    EntityLevel.CONNECTION: (UserRole.VIEWER,),
}


def can_create_role(creator: User, role: UserRole) -> bool:
    if role == UserRole.SUPER_ADMIN:
        return creator.role == UserRole.SUPER_ADMIN
    return ROLE_RANK[role] >= ROLE_RANK[creator.role]


def forbid(detail: str = "Outside your area of responsibility") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# --------------------------------------------------------------------------- parents


def parent_level(user: User) -> EntityLevel | None:
    rel = user.parent
    return rel.level if rel else None


def _committee_ids_under(db: Session, rel: UserRelation) -> list[uuid.UUID]:
    if rel.level == EntityLevel.ORGANIZATION:
        rows = (
            db.query(WaterCommittee.id)
            .join(Partner, Partner.id == WaterCommittee.partner_id)
            .filter(Partner.organization_id == rel.organization_id)
        )
        return [r[0] for r in rows]
    if rel.level == EntityLevel.PARTNER:
        rows = db.query(WaterCommittee.id).filter(WaterCommittee.partner_id == rel.partner_id)
        return [r[0] for r in rows]
    if rel.level == EntityLevel.WATER_COMMITTEE:
        return [rel.water_committee_id]
    if rel.level == EntityLevel.CONNECTION:
        row = (
            db.query(Connection.water_committee_id)
            .filter(Connection.id == rel.connection_id)
            .first()
        )
        return [row[0]] if row else []
    return []


def visible_organization_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    if user.role == UserRole.SUPER_ADMIN:
        return None
    rel = user.parent
    if rel is None:
        return []
    if rel.level == EntityLevel.ORGANIZATION:
        return [rel.organization_id]
    partner_ids = visible_partner_ids(db, user) or []
    rows = db.query(Partner.organization_id).filter(Partner.id.in_(partner_ids))
    return sorted({r[0] for r in rows if r[0]})


def visible_partner_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    if user.role == UserRole.SUPER_ADMIN:
        return None
    rel = user.parent
    if rel is None:
        return []
    if rel.level == EntityLevel.ORGANIZATION:
        rows = db.query(Partner.id).filter(Partner.organization_id == rel.organization_id)
        return [r[0] for r in rows]
    if rel.level == EntityLevel.PARTNER:
        return [rel.partner_id]
    committee_ids = visible_committee_ids(db, user) or []
    rows = db.query(WaterCommittee.partner_id).filter(WaterCommittee.id.in_(committee_ids))
    return sorted({r[0] for r in rows})


def visible_committee_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Committees this user may see, or None for no restriction (super admin)."""
    if user.role == UserRole.SUPER_ADMIN:
        return None
    rel = user.parent
    if rel is None:
        return []
    return _committee_ids_under(db, rel)


def visible_connection_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Connections this user may see, or None for "every connection in the visible committees"."""
    if user.role == UserRole.SUPER_ADMIN:
        return None
    rel = user.parent
    if rel is None:
        return []
    if rel.level == EntityLevel.CONNECTION:
        return [rel.connection_id]
    if rel.access_all_children:
        return None
    children = user.children
    if not children:
        return None
    ids: set[uuid.UUID] = {c.connection_id for c in children if c.connection_id}
    community_ids = [c.community_id for c in children if c.community_id]
    if community_ids:
        rows = db.query(Connection.id).filter(Connection.community_id.in_(community_ids))
        ids.update(r[0] for r in rows)
    return list(ids)


def visible_community_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Communities (groupings) this user may see, or None for no restriction."""
    if user.role == UserRole.SUPER_ADMIN:
        return None
    rel = user.parent
    if rel is None:
        return []
    if rel.level == EntityLevel.CONNECTION:
        row = db.query(Connection.community_id).filter(Connection.id == rel.connection_id).first()
        return [row[0]] if row and row[0] else []
    committee_ids = _committee_ids_under(db, rel)
    if not rel.access_all_children and user.children:
        explicit = {c.community_id for c in user.children if c.community_id}
        conn_ids = [c.connection_id for c in user.children if c.connection_id]
        if conn_ids:
            rows = db.query(Connection.community_id).filter(Connection.id.in_(conn_ids))
            explicit.update(r[0] for r in rows if r[0])
        return list(explicit)
    rows = db.query(Community.id).filter(Community.water_committee_id.in_(committee_ids))
    return [r[0] for r in rows]


# --------------------------------------------------------------------------- queries


def _restrict(query: Query, column, ids: list[uuid.UUID] | None) -> Query:
    if ids is None:
        return query
    return query.filter(column.in_(ids)) if ids else query.filter(False)


def scope_committees(db: Session, user: User, query: Query) -> Query:
    return _restrict(query, WaterCommittee.id, visible_committee_ids(db, user))


def scope_partners(db: Session, user: User, query: Query) -> Query:
    return _restrict(query, Partner.id, visible_partner_ids(db, user))


def scope_communities(db: Session, user: User, query: Query) -> Query:
    return _restrict(query, Community.id, visible_community_ids(db, user))


def scope_connections(db: Session, user: User, query: Query) -> Query:
    connection_ids = visible_connection_ids(db, user)
    if connection_ids is not None:
        return _restrict(query, Connection.id, connection_ids)
    return _restrict(query, Connection.water_committee_id, visible_committee_ids(db, user))


# --------------------------------------------------------------------------- checks


def can_see_committee(db: Session, user: User, committee_id: uuid.UUID) -> bool:
    ids = visible_committee_ids(db, user)
    return ids is None or committee_id in ids


def can_see_community(db: Session, user: User, community_id: uuid.UUID) -> bool:
    ids = visible_community_ids(db, user)
    return ids is None or community_id in ids


def can_see_connection(db: Session, user: User, connection: Connection) -> bool:
    connection_ids = visible_connection_ids(db, user)
    if connection_ids is not None:
        return connection.id in connection_ids
    return can_see_committee(db, user, connection.water_committee_id)


def can_see_partner(db: Session, user: User, partner_id: uuid.UUID) -> bool:
    ids = visible_partner_ids(db, user)
    return ids is None or partner_id in ids


def can_see_organization(db: Session, user: User, organization_id: uuid.UUID) -> bool:
    ids = visible_organization_ids(db, user)
    return ids is None or organization_id in ids


def can_manage_level(user: User, level: EntityLevel) -> bool:
    """Admins create/delete at their parent level and below; editors only edit."""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    if user.role != UserRole.ADMIN:
        return False
    own = parent_level(user)
    if own is None:
        return False
    return LEVEL_ORDER.index(level) >= LEVEL_ORDER.index(own)


def require_manage(user: User, level: EntityLevel) -> None:
    if not can_manage_level(user, level):
        raise forbid("Only an administrator at this level or above can do that")


def require_committee(db: Session, user: User, committee_id: uuid.UUID) -> WaterCommittee:
    committee = db.query(WaterCommittee).filter(WaterCommittee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Water committee not found"
        )
    if not can_see_committee(db, user, committee_id):
        raise forbid()
    return committee


def require_community(db: Session, user: User, community_id: uuid.UUID) -> Community:
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    if not can_see_community(db, user, community_id):
        raise forbid()
    return community


def require_connection(db: Session, user: User, connection_id: uuid.UUID) -> Connection:
    connection = db.query(Connection).filter(Connection.id == connection_id).first()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if not can_see_connection(db, user, connection):
        raise forbid()
    return connection


def require_partner(db: Session, user: User, partner_id: uuid.UUID) -> Partner:
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    if not can_see_partner(db, user, partner_id):
        raise forbid()
    return partner


def set_parent(
    user: User,
    level: EntityLevel,
    entity_id: uuid.UUID,
    access_all_children: bool = True,
) -> None:
    user.relations = [r for r in user.relations if r.relation_type != RelationType.PARENT]
    user.relations.append(
        UserRelation.for_entity(level, entity_id, RelationType.PARENT, access_all_children)
    )


def set_children(
    user: User,
    community_ids: list[uuid.UUID] = (),
    connection_ids: list[uuid.UUID] = (),
) -> None:
    user.relations = [r for r in user.relations if r.relation_type != RelationType.CHILD]
    for cid in community_ids:
        user.relations.append(UserRelation.for_entity(EntityLevel.COMMUNITY, cid))
    for cid in connection_ids:
        user.relations.append(UserRelation.for_entity(EntityLevel.CONNECTION, cid))
    parent = user.parent
    if parent is not None:
        parent.access_all_children = not (community_ids or connection_ids)
