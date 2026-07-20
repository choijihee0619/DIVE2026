"""CODEF 부동산등기부 클라이언트 (샌드박스 검증 완료 2026-07-20).

- OAuth client_credentials 토큰을 발급받아 프로세스 내 캐시(만료 60초 전 갱신)
- 열람용 비밀번호는 CODEF RSA 공개키(PKCS1 v1.5)로 암호화해 전송
- 샌드박스는 주소와 무관하게 고정 샘플 등기부(집합건물, 근저당·압류 포함)를 반환하므로
  데모에는 충분하다. 운영 전환 시 CODEF_ENV=prod + 상품 계약 필요.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from urllib.parse import unquote

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding

from app.core.config import BACKEND_DIR, get_settings

logger = logging.getLogger(__name__)

REGISTER_PATH = "/v1/kr/public/ck/real-estate-register/status"

_token_cache: dict[str, object] = {"token": None, "expires_at": 0.0}


class CodefNotConfiguredError(RuntimeError):
    pass


def _creds() -> tuple[str, str, str, str]:
    s = get_settings()
    env = (s.codef_env or "sandbox").lower()
    prefix = "demo" if env == "demo" else "sandbox"
    cid = getattr(s, f"codef_{prefix}_client_id", "")
    sec = getattr(s, f"codef_{prefix}_client_secret", "")
    base = getattr(s, f"codef_{prefix}_base_url", "")
    if not (cid and sec and base):
        raise CodefNotConfiguredError("CODEF 클라이언트 키가 설정되지 않았습니다.")
    return cid, sec, base, s.codef_oauth_url


def _encrypted_password() -> str:
    s = get_settings()
    key_path = Path(s.codef_public_key_path)
    if not key_path.is_absolute():
        key_path = BACKEND_DIR / key_path
    key_text = key_path.read_text().strip()
    if "BEGIN" not in key_text:
        key_text = f"-----BEGIN PUBLIC KEY-----\n{key_text}\n-----END PUBLIC KEY-----"
    pub = serialization.load_pem_public_key(key_text.encode())
    cipher = pub.encrypt(s.codef_register_password.encode(), rsa_padding.PKCS1v15())
    return base64.b64encode(cipher).decode()


async def _get_token(client: httpx.AsyncClient) -> str:
    now = time.monotonic()
    if _token_cache["token"] and now < float(_token_cache["expires_at"]):
        return str(_token_cache["token"])
    cid, sec, _base, oauth_url = _creds()
    resp = await client.post(
        oauth_url, auth=(cid, sec),
        data={"grant_type": "client_credentials", "scope": "read"},
    )
    resp.raise_for_status()
    body = resp.json()
    token = body["access_token"]
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + int(body.get("expires_in", 3600)) - 60
    return token


async def fetch_register(address: str, realty_type: str = "1", timeout: float = 60.0) -> dict:
    """등기부 열람 호출. 성공 시 CODEF data(dict) 반환, 실패 시 예외."""
    _cid, _sec, base, _oauth = _creds()
    async with httpx.AsyncClient(timeout=timeout) as client:
        token = await _get_token(client)
        payload = {
            "organization": "0002",
            "phoneNo": "01012345678",
            "password": _encrypted_password(),
            "inquiryType": "1",
            "issueType": "1",
            "realtyType": realty_type,
            "recordStatus": "0",
            "address": address,
            "addrSido": address.split()[0] if address else "",
        }
        resp = await client.post(
            base + REGISTER_PATH,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            content=json.dumps(payload),
        )
        resp.raise_for_status()
        body = json.loads(unquote(resp.text))
        code = body.get("result", {}).get("code")
        if code != "CF-00000":
            raise RuntimeError(f"CODEF 오류: {code} {body.get('result', {}).get('message')}")
        return body
