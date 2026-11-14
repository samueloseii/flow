import uuid

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole
from app.models.user_relation import EntityLevel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    phone: str | None = None
    is_active: bool = True
    # Where the account sits: its parent entity and whether it sees the whole branch.
    parent_level: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    access_all_children: bool = True
    # Restricted accounts: the groupings / connections they may see.
    community_ids: list[str] = []
    connection_ids: list[str] = []
    # Convenience: the water committee the account works in, if any.
    water_committee_id: str | None = None
    partner_id: str | None = None
    organization_id: str | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None
    role: UserRole = UserRole.VIEWER
    preferred_language: str = "es"
    parent_level: EntityLevel | None = None
    parent_id: uuid.UUID | None = None
    # Leave both empty for access to everything below the parent.
    community_ids: list[uuid.UUID] = []
    connection_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: UserRole | None = None
    parent_level: EntityLevel | None = None
    parent_id: uuid.UUID | None = None
    community_ids: list[uuid.UUID] | None = None
    connection_ids: list[uuid.UUID] | None = None


class PasswordReset(BaseModel):
    new_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
