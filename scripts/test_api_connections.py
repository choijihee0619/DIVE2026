#!/usr/bin/env python3
"""
API 연결 테스트 스크립트
작성일: 2026-07-14

backend/backend_env_설정_260714.txt 또는 backend/.env 에서 키를 읽어
각 외부 API에 최소 1회 호출을 시도하고 결과를 JSON으로 저장한다.

사용법:
  python scripts/test_api_connections.py
"""

from __future__ import annotations

import json
import ssl
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DATA_ROOT = ROOT / "개별수집데이터 및 API"
METADATA = DATA_ROOT / "metadata"
OUTPUT = METADATA / "api_connection_test_260714.json"

KST = timezone(timedelta(hours=9))

try:
    import certifi
except ImportError:
    HTTPS_CONTEXT = ssl.create_default_context()
else:
    HTTPS_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def key_query_part(key_param: str, key_value: str) -> str:
    if "%" in key_value:
        return f"{key_param}={key_value}"
    return f"{key_param}={quote_plus(key_value)}"


def build_query(key_param: str, key_value: str, params: dict) -> str:
    return f"{key_query_part(key_param, key_value)}&{urlencode(params)}"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for candidate in [BACKEND / ".env", BACKEND / "backend_env_설정_260714.txt"]:
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
        break
    return env


def http_get(url: str, timeout: int = 15) -> tuple[int, str]:
    req = Request(url, headers={"User-Agent": "DIVE2026-API-Test/1.0"})
    try:
        with urlopen(req, timeout=timeout, context=HTTPS_CONTEXT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:2000]
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:2000]
        return e.code, body
    except URLError as e:
        return 0, str(e.reason)


def http_post(url: str, body: dict, timeout: int = 15) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={
            "User-Agent": "DIVE2026-API-Test/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout, context=HTTPS_CONTEXT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:2000]
    except HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:2000]
        return e.code, body_text
    except URLError as e:
        return 0, str(e.reason)


def result(api: str, status: int, ok: bool, body: str, **extra: object) -> dict:
    out = {"api": api, "http_status": status, "ok": ok, **extra}
    if not ok:
        out["response_body"] = body[:2000]
    return out


def judge_ok(name: str, status: int, body: str) -> bool:
    if status != 200:
        return False
    if name == "juso":
        return '"errorCode":"0"' in body or '"errorCode": "0"' in body
    if name == "dart":
        try:
            data = json.loads(body)
            return data.get("status") == "000" or "list" in data
        except json.JSONDecodeError:
            return False
    if name == "business_status":
        try:
            data = json.loads(body)
            return data.get("status_code") == "OK" or "data" in data
        except json.JSONDecodeError:
            return False
    if name in ("rtms", "building", "official_price_apt", "official_price_land"):
        return "<resultCode>00</resultCode>" in body or '"totalCount"' in body or "totalCount" in body
    return True


def test_juso(key: str) -> dict:
    params = build_query("confmKey", key, {
        "keyword": "서울특별시 강남구 테헤란로 152",
        "currentPage": "1",
        "countPerPage": "1",
        "resultType": "json",
    })
    url = f"https://business.juso.go.kr/addrlink/addrLinkApi.do?{params}"
    status, body = http_get(url)
    return result("juso", status, judge_ok("juso", status, body), body)


def test_rtms(key: str) -> dict:
    params = build_query("serviceKey", key, {
        "LAWD_CD": "11680",
        "DEAL_YMD": "202506",
        "pageNo": "1",
        "numOfRows": "1",
    })
    url = f"https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade?{params}"
    status, body = http_get(url)
    return result("rtms_apt_trade", status, judge_ok("rtms", status, body), body)


def test_building(key: str, endpoint: str = "/1613000/BldRgstHubService/getBrTitleInfo") -> dict:
    params = build_query("serviceKey", key, {
        "sigunguCd": "11680",
        "bjdongCd": "10300",
        "bun": "0012",
        "ji": "0000",
        "pageNo": "1",
        "numOfRows": "1",
        "_type": "json",
    })
    url = f"https://apis.data.go.kr{endpoint}?{params}"
    status, body = http_get(url)
    return result("building_registry", status, judge_ok("building", status, body), body)


def test_business(key: str) -> dict:
    url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?{key_query_part('serviceKey', key)}"
    status, body = http_post(url, {"b_no": ["1248100998"]})
    return result("business_status", status, judge_ok("business_status", status, body), body)


def test_dart(key: str) -> dict:
    params = urlencode({
        "crtfc_key": key,
        "corp_code": "00126380",
        "bgn_de": "20250101",
        "end_de": "20260714",
        "page_no": "1",
    })
    url = f"https://opendart.fss.or.kr/api/list.json?{params}"
    status, body = http_get(url)
    return result("dart_list", status, judge_ok("dart", status, body), body)


def test_official_price(name: str, key: str) -> dict:
    return {
        "api": name,
        "ok": False,
        "error_class": "manual_config_required",
        "error_message": "디지털트윈국토/VWorld 인증키는 등록 서비스 URL과 실제 API URL/레이어명이 맞아야 하므로 연결 테스트에서 직접 호출하지 않음.",
        "key_masked": key[:4] + "…" + key[-4:] if len(key) > 8 else "****",
    }


def test_codef(env: dict) -> dict:
    codef_env = env.get("CODEF_ENV", "sandbox").lower()
    if codef_env == "demo":
        base = env.get("CODEF_DEMO_BASE_URL", "https://development.codef.io")
        client_id = env.get("CODEF_DEMO_CLIENT_ID", "")
        client_secret = env.get("CODEF_DEMO_CLIENT_SECRET", "")
    else:
        base = env.get("CODEF_SANDBOX_BASE_URL", "https://sandbox.codef.io")
        client_id = env.get("CODEF_SANDBOX_CLIENT_ID", "")
        client_secret = env.get("CODEF_SANDBOX_CLIENT_SECRET", "")
    oauth_url = env.get("CODEF_OAUTH_URL", "https://oauth.codef.io/oauth/token")

    if not client_id or not client_secret:
        return {"api": "codef_token", "ok": False, "note": "CODEF credentials missing"}

    import base64
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = Request(
        oauth_url,
        data=b"grant_type=client_credentials&scope=read",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15, context=HTTPS_CONTEXT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ok = "access_token" in body
            token_meta = {"token_issued": ok}
            try:
                parsed = json.loads(body)
                token_meta.update({
                    "token_type": parsed.get("token_type"),
                    "expires_in": parsed.get("expires_in"),
                    "scope": parsed.get("scope"),
                })
            except json.JSONDecodeError:
                pass
            return {"api": "codef_token", "env": codef_env, "oauth_url": oauth_url,
                    "api_base_url": base, "http_status": resp.status, "ok": ok,
                    "token": token_meta}
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return result("codef_token", e.code, False, body, env=codef_env)
    except URLError as e:
        return result("codef_token", 0, False, str(e.reason), env=codef_env)


def main() -> int:
    env = load_env()
    if not env:
        print("ERROR: backend/.env 또는 backend_env_설정_260714.txt 없음", file=sys.stderr)
        return 1

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    results: list[dict] = [{"tested_at": now, "purpose": env.get("APP_PURPOSE", "")}]

    tests = []
    if key := env.get("JUSO_API_KEY"):
        tests.append(lambda: test_juso(key))
    if key := env.get("DATA_GO_KR_API_KEY"):
        tests.extend([
            lambda k=key: test_rtms(k),
            lambda k=key, e=env.get("BUILDING_REGISTRY_ENDPOINT", "/1613000/BldRgstHubService/getBrTitleInfo"): test_building(k, e),
            lambda k=key: test_business(k),
        ])
    if key := env.get("DART_API_KEY"):
        tests.append(lambda: test_dart(key))
    if key := env.get("OFFICIAL_PRICE_APT_API_KEY"):
        tests.append(lambda k=key: test_official_price("official_price_apt", k))
    if key := env.get("OFFICIAL_PRICE_HOUSE_API_KEY"):
        tests.append(lambda k=key: test_official_price("official_price_house", k))
    if key := env.get("OFFICIAL_PRICE_LAND_API_KEY"):
        tests.append(lambda k=key: test_official_price("official_price_land", k))
    tests.append(lambda: test_codef(env))

    for fn in tests:
        try:
            result = fn()
            results.append(result)
            mark = "OK" if result.get("ok") else "FAIL"
            print(f"[{mark}] {result.get('api')} (HTTP {result.get('http_status', '-')})")
        except Exception as exc:
            results.append({"api": "unknown", "ok": False, "error": str(exc)})
            print(f"[FAIL] {exc}")

    METADATA.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {OUTPUT}")

    ok_count = sum(1 for r in results if isinstance(r, dict) and r.get("ok"))
    total = sum(1 for r in results if isinstance(r, dict) and "api" in r)
    print(f"성공 {ok_count}/{total}")
    return 0 if ok_count == total else 2


if __name__ == "__main__":
    sys.exit(main())
