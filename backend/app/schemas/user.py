from __future__ import annotations

from pydantic import BaseModel

from app.schemas.auth import UserPublic


class UserListResponse(BaseModel):
    items: list[UserPublic]
    pagination: dict
