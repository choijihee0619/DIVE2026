from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    role: UserRole = UserRole.TENANT


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserPublic(BaseModel):
    user_id: str
    role: str
    display_name: str
    email: str | None = None
    created_at: str | None = None
    last_login_at: str | None = None


class LoginData(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserPublic
