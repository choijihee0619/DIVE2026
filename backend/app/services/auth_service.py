from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import InvalidTokenError, StateConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginData, LoginRequest, SignupRequest, UserPublic
from app.utils.datetime_utils import now_kst_iso, new_uuid


class AuthService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._users = UserRepository(db)

    async def signup(self, payload: SignupRequest) -> UserPublic:
        existing = await self._users.get_by_email(payload.email)
        if existing:
            raise StateConflictError("이미 가입된 이메일입니다.")

        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "email": payload.email,
            "password_hash": hash_password(payload.password),
            "role": payload.role.value,
            "display_name": payload.display_name,
            "is_active": True,
            "created_at": now,
            "last_login_at": None,
        }
        await self._users.insert(doc)
        return UserPublic(
            user_id=doc["_id"],
            role=doc["role"],
            display_name=doc["display_name"],
            email=doc["email"],
            created_at=doc["created_at"],
        )

    async def login(self, payload: LoginRequest) -> LoginData:
        user = await self._users.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise InvalidTokenError("이메일 또는 비밀번호가 올바르지 않습니다.")
        if not user.get("is_active", True):
            raise InvalidTokenError("비활성화된 계정입니다.")

        token, expires_in = create_access_token(user["_id"], user["role"])
        await self._users.update_fields(user["_id"], {"last_login_at": now_kst_iso()})

        return LoginData(
            access_token=token,
            expires_in=expires_in,
            user=UserPublic(
                user_id=user["_id"],
                role=user["role"],
                display_name=user["display_name"],
                email=user.get("email"),
            ),
        )

    async def get_me(self, user_id: str) -> UserPublic:
        user = await self._users.get_by_id(user_id)
        if not user:
            raise InvalidTokenError()
        return UserPublic(
            user_id=user["_id"],
            role=user["role"],
            display_name=user["display_name"],
            email=user.get("email"),
            created_at=user.get("created_at"),
            last_login_at=user.get("last_login_at"),
        )
