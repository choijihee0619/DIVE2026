"""SHA-256 해시 유틸. Blockchain_설계서_260714.md 7.1절: 오프체인/문서 해시는 SHA-256으로 통일."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def canonical_json(payload: dict[str, Any]) -> str:
    """정렬된 키, 공백 제거, null 필드 제외. Blockchain_설계서 7.3절 canonical JSON 규칙."""
    cleaned = {k: v for k, v in payload.items() if v is not None}
    return json.dumps(cleaned, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_json(payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(payload).encode("utf-8"))
