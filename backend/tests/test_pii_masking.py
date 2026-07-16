from __future__ import annotations

from app.utils.pii_masking import mask_pii, truncate_snippet


def test_mask_phone_number():
    assert mask_pii("연락처는 010-1234-5678 입니다") == "연락처는 010-****-5678 입니다"


def test_mask_rrn():
    masked = mask_pii("주민등록번호 901010-1234567")
    assert "901010-1******" == masked.split("주민등록번호 ")[1]


def test_mask_email():
    masked = mask_pii("문의: abcdef@example.com")
    assert "@example.com" in masked
    assert "abcdef" not in masked


def test_mask_account_like_number():
    masked = mask_pii("계좌번호로 추정: 1234567890123")
    assert "1234567890123" not in masked


def test_mask_pii_none_safe():
    assert mask_pii(None) == ""


def test_truncate_snippet_limits_length_and_masks():
    long_text = "연락처 010-9999-8888 " + "상담내용 " * 100
    snippet = truncate_snippet(long_text, max_len=50)
    assert len(snippet) <= 55
    assert "010-9999-8888" not in snippet
    assert "010-****-8888" in snippet
