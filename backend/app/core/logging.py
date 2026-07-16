"""구조화(JSON) 로깅 설정 + 민감정보 마스킹 필터. 시크릿/PII를 로그에 원문으로 남기지 않는다."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.utils.pii_masking import mask_pii

_SENSITIVE_KEYS = {"password", "secret_key", "jwt_secret_key", "openai_api_key", "mongodb_uri", "token", "access_token"}


class PiiMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_pii(str(record.getMessage()))
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(debug: bool = True) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(PiiMaskingFilter())
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    # pymongo/motor의 DEBUG 로그는 지나치게 장황하고 접속정보 관련 노이즈가 많아 WARNING으로 고정한다.
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
