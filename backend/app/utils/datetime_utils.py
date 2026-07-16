"""날짜/시간 유틸. API 응답은 KST(+09:00) 오프셋 포함 ISO 8601로 통일한다."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def now_kst_iso() -> str:
    return datetime.now(KST).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


def new_request_id(prefix: str = "req") -> str:
    stamp = datetime.now(KST).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"
