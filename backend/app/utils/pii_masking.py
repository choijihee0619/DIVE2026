"""개인정보 최소 방어 마스킹 유틸리티.

주의: 이 모듈은 "완벽한 개인정보 탐지"를 보장하지 않는다. 정규식 기반 최소 방어 로직이며,
자유서술형 텍스트에 포함된 실명·회사명·준식별자까지는 탐지하지 못한다
(개별수집데이터 및 API/metadata/pii_review_260714.md 참고 — 정규식 스캔은 0건이었지만
사람 표본검수 전까지 pii_removed=true로 전환하지 않기로 함).
"""

from __future__ import annotations

import re

_RRN_PATTERN = re.compile(r"\b(\d{6})[-\s]?([1-4]\d{6})\b")
_PHONE_PATTERN = re.compile(r"\b(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})\b")
_LANDLINE_PATTERN = re.compile(r"\b(0(?:2|[3-6]\d))[-.\s]?(\d{3,4})[-.\s]?(\d{4})\b")
_EMAIL_PATTERN = re.compile(r"\b([A-Za-z0-9._%+-]{1,})(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_ACCOUNT_LIKE_PATTERN = re.compile(r"\b\d{10,16}\b")


def _mask_rrn(match: re.Match[str]) -> str:
    return f"{match.group(1)}-{match.group(2)[0]}******"


def _mask_phone(match: re.Match[str]) -> str:
    return f"{match.group(1)}-****-{match.group(3)}"


def _mask_email(match: re.Match[str]) -> str:
    local = match.group(1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(len(local) - len(visible), 3)}{match.group(2)}"


def _mask_account_like(match: re.Match[str]) -> str:
    digits = match.group(0)
    return f"{digits[:2]}{'*' * (len(digits) - 4)}{digits[-2:]}"


def mask_pii(text: str | None) -> str:
    """주민등록번호/전화번호/이메일/계좌추정 숫자열을 마스킹한다. None-safe."""
    if not text:
        return ""
    masked = text
    masked = _RRN_PATTERN.sub(_mask_rrn, masked)
    masked = _PHONE_PATTERN.sub(_mask_phone, masked)
    masked = _LANDLINE_PATTERN.sub(_mask_phone, masked)
    masked = _EMAIL_PATTERN.sub(_mask_email, masked)
    masked = _ACCOUNT_LIKE_PATTERN.sub(_mask_account_like, masked)
    return masked


def truncate_snippet(text: str | None, max_len: int = 160) -> str:
    """상담 원문 전체 노출을 방지하기 위해 길이를 제한한 뒤 마스킹한다."""
    if not text:
        return ""
    snippet = text if len(text) <= max_len else text[:max_len].rstrip() + "…"
    return mask_pii(snippet)
