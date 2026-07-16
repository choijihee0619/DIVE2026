from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserPublic
from app.schemas.common import build_pagination


class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._users = UserRepository(db)

    async def list_users(self, page: int, size: int, role: str | None, search: str | None):
        items, total = await self._users.list_paginated((page - 1) * size, size, role=role, search=search)
        users = [
            UserPublic(
                user_id=item["_id"],
                role=item["role"],
                display_name=item["display_name"],
                email=item.get("email"),
                created_at=item.get("created_at"),
                last_login_at=item.get("last_login_at"),
            )
            for item in items
        ]
        return users, build_pagination(page, size, total)
