import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, FIELD_ROLES, get_current_user, require_role
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.connection import Connection
from app.models.organization import Organization
from app.models.partner import Partner
from app.models.user import User, UserRole
from app.models.user_relation import EntityLevel
from app.models.water_committee import WaterCommittee
from app.services.scope import (
    LEVEL_ORDER,
    ROLE_LABELS,
    ROLES_AT_LEVEL,
    _committee_ids_under,
    can_create_role,
    can_see_committee,
    can_see_connection,
    can_see_organization,
    can_see_partner,
    forbid,
    parent_level,
    require_community,
    require_connection,
    set_children,
    set_parent,
    visible_committee_ids,
    visible_organization_ids,
    visible_partner_ids,
)
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    PasswordReset,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _entity_name(db: Session, rel) -> str | None:
    model = {
        EntityLevel.ORGANIZATION: Organization,
        EntityLevel.PARTNER: Partner,
        EntityLevel.WATER_COMMITTEE: WaterCommittee,
        EntityLevel.CONNECTION: Connection,
    }[rel.level]
    row = db.query(model).filter(model.id == rel.entity_id).first()
    if row is None:
        return None
    return getattr(row, "name", None) or getattr(row, "contact_name", None)


def _user_response(db: Session, user: User) -> UserResponse:
    rel = user.parent
    committee_ids = visible_committee_ids(db, user) or []
    partner_ids = visible_partner_ids(db, user) or []
    org_ids = visible_organization_ids(db, user) or []
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        phone=user.phone,
        is_active=user.is_active,
        parent_level=rel.level.value if rel else None,
        parent_id=str(rel.entity_id) if rel else None,
        parent_name=_entity_name(db, rel) if rel else None,
        access_all_children=rel.access_all_children if rel else True,
        community_ids=[str(c.community_id) for c in user.children if c.community_id],
        connection_ids=[str(c.connection_id) for c in user.children if c.connection_id],
        water_committee_id=str(committee_ids[0]) if len(committee_ids) == 1 else None,
        partner_id=str(partner_ids[0]) if len(partner_ids) == 1 else None,
        organization_id=str(org_ids[0]) if len(org_ids) == 1 else None,
    )


def _user_in_scope(db: Session, actor: User, user: User) -> bool:
    """A user is in my scope when its parent entity is one I may see."""
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    if user.role == UserRole.SUPER_ADMIN:
        return False
    rel = user.parent
    if rel is None:
        return False
    if rel.level == EntityLevel.ORGANIZATION:
        return can_see_organization(db, actor, rel.organization_id)
    if rel.level == EntityLevel.PARTNER:
        return can_see_partner(db, actor, rel.partner_id)
    if rel.level == EntityLevel.WATER_COMMITTEE:
        return can_see_committee(db, actor, rel.water_committee_id)
    connection = db.query(Connection).filter(Connection.id == rel.connection_id).first()
    return connection is not None and can_see_connection(db, actor, connection)


def _check_role(actor: User, role: UserRole) -> None:
    if not can_create_role(actor, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only give people a role at your level or below",
        )


def _check_parent(db: Session, actor: User, level: EntityLevel, entity_id: uuid.UUID, role: UserRole) -> None:
    if level == EntityLevel.COMMUNITY:
        raise HTTPException(status_code=400, detail="Accounts belong to an organization, partner, water committee or connection")
    if role not in ROLES_AT_LEVEL[level]:
        raise HTTPException(
            status_code=400,
            detail=f"A {ROLE_LABELS[role].lower()} cannot be attached to a {level.value.replace('_', ' ')}",
        )
    if level == EntityLevel.ORGANIZATION:
        ok = can_see_organization(db, actor, entity_id)
        exists = db.query(Organization).filter(Organization.id == entity_id).first() is not None
    elif level == EntityLevel.PARTNER:
        ok = can_see_partner(db, actor, entity_id)
        exists = db.query(Partner).filter(Partner.id == entity_id).first() is not None
    elif level == EntityLevel.WATER_COMMITTEE:
        ok = can_see_committee(db, actor, entity_id)
        exists = db.query(WaterCommittee).filter(WaterCommittee.id == entity_id).first() is not None
    else:
        connection = db.query(Connection).filter(Connection.id == entity_id).first()
        exists = connection is not None
        ok = exists and can_see_connection(db, actor, connection)
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent entity not found")
    if not ok:
        raise forbid()
    # Nobody may place an account above their own level.
    if actor.role != UserRole.SUPER_ADMIN:
        own = parent_level(actor)
        if own is None or LEVEL_ORDER.index(level) < LEVEL_ORDER.index(own):
            raise forbid("You can only add people at your level or below")


def _apply_children(
    db: Session,
    actor: User,
    user: User,
    community_ids: list[uuid.UUID] | None,
    connection_ids: list[uuid.UUID] | None,
) -> None:
    if community_ids is None and connection_ids is None:
        return
    community_ids = list(community_ids or [])
    connection_ids = list(connection_ids or [])
    rel = user.parent
    if rel is None or rel.level == EntityLevel.CONNECTION:
        set_children(user)
        return
    committee_ids = _committee_ids_under(db, rel)
    for cid in community_ids:
        community = require_community(db, actor, cid)
        if community.water_committee_id not in committee_ids:
            raise HTTPException(status_code=400, detail="That community is outside the account's water committee")
    for cid in connection_ids:
        connection = require_connection(db, actor, cid)
        if connection.water_committee_id not in committee_ids:
            raise HTTPException(status_code=400, detail="That connection is outside the account's water committee")
    set_children(user, community_ids, connection_ids)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is disabled. Ask your administrator to restore it.",
        )
    expires = (
        timedelta(minutes=settings.FIELD_TOKEN_EXPIRE_MINUTES) if user.role in FIELD_ROLES else None
    )
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}, expires_delta=expires
    )
    return TokenResponse(access_token=token)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*ADMIN_ROLES)),
):
    """An administrator sets a new password for someone who lost theirs."""
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not _user_in_scope(db, _, user) or not can_create_role(_, user.role):
        raise forbid()
    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """An administrator corrects someone's details, role or place in the hierarchy."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.role is not None and user.id == current_user.id and payload.role != user.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )
    if not _user_in_scope(db, current_user, user) or not can_create_role(current_user, user.role):
        raise forbid()
    role = payload.role if payload.role is not None else user.role
    if payload.role is not None:
        _check_role(current_user, payload.role)
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone
    user.role = role
    if (payload.parent_level is None) != (payload.parent_id is None):
        raise HTTPException(status_code=400, detail="Give both the parent level and the parent entity")
    if payload.parent_level is not None and role != UserRole.SUPER_ADMIN:
        _check_parent(db, current_user, payload.parent_level, payload.parent_id, role)
        set_parent(user, payload.parent_level, payload.parent_id)
        set_children(user)
    elif user.parent is not None and role not in ROLES_AT_LEVEL[user.parent.level]:
        raise HTTPException(
            status_code=400,
            detail=f"A {ROLE_LABELS[role].lower()} cannot be attached to a {user.parent.level.value.replace('_', ' ')}",
        )
    if role == UserRole.SUPER_ADMIN:
        user.relations = []
    _apply_children(db, current_user, user, payload.community_ids, payload.connection_ids)
    db.commit()
    db.refresh(user)
    return _user_response(db, user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not _user_in_scope(db, current_user, user) or not can_create_role(current_user, user.role):
        raise forbid()
    db.delete(user)
    db.commit()


@router.get("/me", response_model=UserResponse)
def get_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _user_response(db, current_user)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    users = db.query(User).order_by(User.full_name).all()
    return [
        _user_response(db, u)
        for u in users
        if u.id == current_user.id or _user_in_scope(db, current_user, u)
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Only administrators create logins; there is no public sign-up.

    Every account except the super admin belongs to one parent entity.  Leave the parent
    out to attach the new account to the same entity as yourself.
    """
    if current_user.role == UserRole.EDITOR:
        raise forbid("Editors cannot add people")
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    _check_role(current_user, payload.role)
    level, parent_id = payload.parent_level, payload.parent_id
    if payload.role != UserRole.SUPER_ADMIN:
        if level is None or parent_id is None:
            own = current_user.parent
            if own is None:
                raise HTTPException(status_code=400, detail="Choose where this account belongs")
            level, parent_id = own.level, own.entity_id
        _check_parent(db, current_user, level, parent_id, payload.role)
    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        preferred_language=payload.preferred_language,
    )
    if payload.role != UserRole.SUPER_ADMIN:
        set_parent(user, level, parent_id)
    db.add(user)
    db.flush()
    _apply_children(db, current_user, user, payload.community_ids or None, payload.connection_ids or None)
    db.commit()
    db.refresh(user)
    return _user_response(db, user)

