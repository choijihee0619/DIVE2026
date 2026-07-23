from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    # 공개 가입에서 내부 HUG/관리 권한을 발급하지 않는다. 내부 역할은 seed 또는 관리자
    # 프로비저닝 경로로만 생성한다.
    role: Literal[UserRole.TENANT, UserRole.LANDLORD] = UserRole.TENANT


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
