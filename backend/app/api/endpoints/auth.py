import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import ADMIN_ROLES, FIELD_ROLES, get_current_user, require_role
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.community import Community
from app.models.user import User, UserRole
from app.services.scope import (
    can_create_role,
    can_see_committee,
    can_see_community,
    forbid,
    require_household,
    visible_committee_ids,
    visible_community_ids,
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


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        phone=user.phone,
        is_active=user.is_active,
        partner_id=str(user.partner_id) if user.partner_id else None,
        water_committee_id=str(user.water_committee_id) if user.water_committee_id else None,
        community_id=str(user.community_id) if user.community_id else None,
        household_id=str(user.household_id) if user.household_id else None,
        assigned_community_ids=[str(c.id) for c in user.assigned_communities],
    )


def _user_in_scope(db: Session, actor: User, user: User) -> bool:
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    if actor.role == UserRole.PARTNER_ADMIN:
        return user.partner_id == actor.partner_id
    if user.water_committee_id:
        return can_see_committee(db, actor, user.water_committee_id)
    if user.community_id:
        return can_see_community(db, actor, user.community_id)
    return False


def _check_role(actor: User, role: UserRole) -> None:
    if not can_create_role(actor, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only give people a role at your level or below",
        )


def _apply_assignments(db: Session, actor: User, user: User, ids: list[uuid.UUID] | None) -> None:
    if ids is None:
        return
    communities = db.query(Community).filter(Community.id.in_(ids)).all() if ids else []
    for c in communities:
        if not can_see_community(db, actor, c.id):
            raise forbid()
    user.assigned_communities = communities
    if communities and user.community_id is None:
        user.community_id = communities[0].id


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
    """An administrator corrects someone's details, role or community."""
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
    if payload.role is not None:
        _check_role(current_user, payload.role)
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.role is not None:
        user.role = payload.role
    if payload.clear_community:
        user.community_id = None
    elif payload.community_id is not None:
        if not can_see_community(db, current_user, payload.community_id):
            raise forbid()
        user.community_id = payload.community_id
    if payload.clear_water_committee:
        user.water_committee_id = None
    elif payload.water_committee_id is not None:
        if not can_see_committee(db, current_user, payload.water_committee_id):
            raise forbid()
        user.water_committee_id = payload.water_committee_id
    if payload.clear_household or user.role != UserRole.READER:
        user.household_id = None
    elif payload.household_id is not None:
        household = require_household(db, current_user, payload.household_id)
        user.household_id = household.id
        user.community_id = household.community_id
    if payload.partner_id is not None and current_user.role == UserRole.SUPER_ADMIN:
        user.partner_id = payload.partner_id
    _apply_assignments(db, current_user, user, payload.assigned_community_ids)
    db.commit()
    db.refresh(user)
    return _user_response(user)


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
def get_me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    query = db.query(User)
    if current_user.role == UserRole.PARTNER_ADMIN:
        query = query.filter(User.partner_id == current_user.partner_id)
    elif current_user.role != UserRole.SUPER_ADMIN:
        committee_ids = visible_committee_ids(db, current_user)
        community_ids = visible_community_ids(db, current_user) or []
        query = query.filter(
            or_(
                User.water_committee_id.in_(committee_ids) if committee_ids else False,
                User.community_id.in_(community_ids) if community_ids else False,
                User.id == current_user.id,
            )
        )
    return [_user_response(user) for user in query.order_by(User.full_name).all()]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
):
    """Only administrators create logins; there is no public sign-up."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    _check_role(current_user, payload.role)
    if payload.community_id and not can_see_community(db, current_user, payload.community_id):
        raise forbid()
    if payload.water_committee_id and not can_see_committee(
        db, current_user, payload.water_committee_id
    ):
        raise forbid()
    partner_id = (
        payload.partner_id if current_user.role == UserRole.SUPER_ADMIN else current_user.partner_id
    )
    water_committee_id = payload.water_committee_id or current_user.water_committee_id
    community_id = payload.community_id
    household_id = payload.household_id if payload.role == UserRole.READER else None
    if household_id:
        household = require_household(db, current_user, household_id)
        community_id = community_id or household.community_id
    if community_id is None and payload.role in (
        UserRole.OPERATOR,
        UserRole.READER,
        UserRole.TREASURER,
    ):
        community_id = current_user.community_id
    if community_id and water_committee_id is None:
        community = db.query(Community).filter(Community.id == community_id).first()
        if community:
            water_committee_id = community.water_committee_id
            partner_id = partner_id or community.partner_id
    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        preferred_language=payload.preferred_language,
        partner_id=partner_id,
        water_committee_id=water_committee_id,
        community_id=community_id,
        household_id=household_id,
    )
    db.add(user)
    db.flush()
    _apply_assignments(db, current_user, user, payload.assigned_community_ids)
    db.commit()
    db.refresh(user)
    return _user_response(user)
