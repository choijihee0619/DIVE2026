from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class IncidentRepository(BaseRepository):
    collection_name = "incidents"

    async def list_paginated_filtered(
        self,
        skip: int,
        limit: int,
        reporter_user_id: str | None = None,
        status: str | None = None,
        incident_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if reporter_user_id:
            query["reporter_user_id"] = reporter_user_id
        if status:
            query["status"] = status
        if incident_type:
            query["incident_type"] = incident_type
        return await super().list_paginated(query, skip, limit, sort=[("created_at", -1)])
