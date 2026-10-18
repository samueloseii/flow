import uuid

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


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
    partner_id: str | None = None
    water_committee_id: str | None = None
    community_id: str | None = None
    assigned_community_ids: list[str] = []


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None
    role: UserRole = UserRole.READER
    preferred_language: str = "es"
    partner_id: uuid.UUID | None = None
    water_committee_id: uuid.UUID | None = None
    community_id: uuid.UUID | None = None
    assigned_community_ids: list[uuid.UUID] | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: UserRole | None = None
    community_id: uuid.UUID | None = None
    clear_community: bool = False
    water_committee_id: uuid.UUID | None = None
    clear_water_committee: bool = False
    assigned_community_ids: list[uuid.UUID] | None = None


class PasswordReset(BaseModel):
    new_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
