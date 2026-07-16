#!/usr/bin/env python3
"""
외부 API 원본(raw) 데이터 수집 스크립트
작성일: 2026-07-14

데이터수집_및_API가이드_260714.md 4장(연동 순서) · 5장(실패 대응) · 10장(저장 규칙)을 따른다.

동작:
  1. backend/.env (또는 backend_env_설정_260714.txt) 에서 키를 읽는다.
  2. metadata/api_endpoints_260714.yaml 에 정의된 각 API를 순서대로 호출한다 (Retry 2회, timeout 15초).
  3. 성공 시: 응답을 raw/{raw_save_dir}/raw_{api}_{YYYYMMDD}_live.json 로 저장 (source_system=api_live).
  4. 실패 시 (가이드 5장 Fallback 정책): mock/ 의 대응 파일로 대체하여
     raw/{raw_save_dir}/raw_{api}_{YYYYMMDD}_mock_fallback.json 로 저장 (source_system=mock),
     실패 사유(error_class/error_message)를 함께 기록한다.
  5. 전체 결과를 metadata/api_connection_test_260714.json 에 갱신 저장한다.

이 스크립트는 실행 환경의 아웃바운드 네트워크 정책에 따라 실제 API 호출이 차단될 수 있다.
차단된 경우에도 스크립트는 실패하지 않고, 가이드가 정의한 Fallback 경로(Mock 저장)를 그대로 수행한다.
실제 키가 유효한지 최종 확인하려면 아웃바운드 네트워크가 열려 있는 환경(예: 로컬 PC)에서 다시 실행한다.

사용법:
  cd DIVE2026
  python scripts/collect_raw_data.py
"""

from __future__ import annotations

import json
import ssl
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import yaml

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DATA_ROOT = ROOT / "개별수집데이터 및 API"
METADATA = DATA_ROOT / "metadata"
MOCK_DIR = DATA_ROOT / "mock"
ENDPOINTS_FILE = METADATA / "api_endpoints_260714.yaml"
CONN_TEST_FILE = METADATA / "api_connection_test_260714.json"

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y%m%d")
RETRY_COUNT = 2
TIMEOUT_SEC = 15

try:
    import certifi
except ImportError:
    HTTPS_CONTEXT = ssl.create_default_context()
else:
    HTTPS_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# 가이드 5장 Fallback 표 + 6장 Mock 목록 매핑.
# juso(도로명주소)·building_registry(건축물대장)는 가이드 5장에 Fallback으로 명시되어 있으나
# 6.1절 Mock 11종 목록에는 대응 파일이 없어 이번 작업에서 mock_address_fallback.json /
# mock_building_fallback.json 두 개를 신규로 채워 넣었다 (기존 11종 목록은 그대로 유지).
MOCK_FALLBACK_MAP = {
    "juso": "mock_address_fallback.json",
    "rtms_apt_trade": "mock_transaction_empty.json",
    "building_registry": "mock_building_fallback.json",
    "business_status": "mock_business_closed.json",
    "codef_registry": "mock_registry_normal.json",
    "dart_list": "mock_dart_not_found.json",
    "official_price_apt": "mock_official_price_success.json",
    "official_price_house": "mock_official_price_success.json",
    "official_price_land": "mock_official_price_success.json",
}

# 실 호출용 샘플 파라미터 (연결 확인 및 raw 샘플 1건 저장 목적, 가이드 호출예시 기준)
SAMPLE_PARAMS = {
    "juso": {
        "keyword": "서울특별시 강남구 테헤란로 152",
        "currentPage": "1",
        "countPerPage": "1",
        "resultType": "json",
    },
    "rtms_apt_trade": {"LAWD_CD": "11680", "DEAL_YMD": "202506", "pageNo": "1", "numOfRows": "1"},
    "building_registry": {
        "sigunguCd": "11680", "bjdongCd": "10300", "bun": "0012", "ji": "0000",
        "pageNo": "1", "numOfRows": "1", "_type": "json",
    },
    "dart_list": {"corp_code": "00126380", "bgn_de": "20250101", "end_de": TODAY, "page_no": "1"},
    "official_price_apt": {
        "pnu": "1168010300100120000", "stdrYear": "2024", "format": "json",
        "dongNm": "101", "hoNm": "101", "pageNo": "1", "numOfRows": "1",
    },
    "official_price_house": {
        "pnu": "1168010300100120000", "stdrYear": "2024", "format": "json",
        "pageNo": "1", "numOfRows": "1",
    },
    "official_price_land": {
        "pnu": "1168010300100120000", "stdrYear": "2024", "format": "json",
        "pageNo": "1", "numOfRows": "1",
    },
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for candidate in [BACKEND / ".env", BACKEND / "backend_env_설정_260714.txt"]:
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
        break
    return env


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "…" + value[-4:]


def classify_error(exc: Exception) -> str:
    msg = str(exc)
    if "blocked-by-allowlist" in msg or "403" in msg and "proxy" in msg.lower():
        return "network_blocked_by_sandbox_proxy"
    if isinstance(exc, HTTPError):
        if exc.code in (401, 403):
            return "auth_error"
        return f"http_error_{exc.code}"
    if isinstance(exc, URLError):
        reason = str(exc.reason)
        if "CERTIFICATE_VERIFY_FAILED" in reason or "certificate" in reason.lower():
            return "network_blocked_or_tls_intercepted"
        if "Tunnel connection failed" in reason or "403" in reason:
            return "network_blocked_by_sandbox_proxy"
        return "connection_error"
    return "unknown_error"


def http_call(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> dict:
    hdrs = {"User-Agent": "DIVE2026-DataCollector/1.0"}
    hdrs.update(headers or {})
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_COUNT + 2):  # 최초 1회 + Retry 2회
        req = Request(url, data=data, headers=hdrs, method=method)
        try:
            with urlopen(req, timeout=TIMEOUT_SEC, context=HTTPS_CONTEXT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return {"ok": True, "http_status": resp.status, "body": body, "attempts": attempt}
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            last_exc = e
            return {"ok": False, "http_status": e.code, "body": body, "attempts": attempt,
                     "error_class": classify_error(e), "error_message": str(e)}
        except URLError as e:
            last_exc = e
            if attempt <= RETRY_COUNT:
                time.sleep(0.5)
                continue
            return {"ok": False, "http_status": None, "body": "", "attempts": attempt,
                     "error_class": classify_error(e), "error_message": str(e.reason)}
    return {"ok": False, "http_status": None, "body": "", "attempts": RETRY_COUNT + 1,
             "error_class": classify_error(last_exc) if last_exc else "unknown_error",
             "error_message": str(last_exc) if last_exc else "unknown"}


def encoded_query(params: dict) -> str:
    return urlencode(params)


def key_query_part(key_param: str, key_value: str) -> str:
    # 공공데이터포털 Encoding 키는 이미 %2F 등이 들어 있으므로 다시 urlencode하면
    # %252F처럼 이중 인코딩된다. Decoding 키는 여기서 1회만 인코딩한다.
    if "%" in key_value:
        return f"{key_param}={key_value}"
    return f"{key_param}={quote_plus(key_value)}"


def build_url(base_url: str, endpoint: str, key_param: str | None, key_value: str, extra: dict) -> str:
    query_parts = []
    if key_param:
        query_parts.append(key_query_part(key_param, key_value))
    if extra:
        query_parts.append(encoded_query(extra))
    return f"{base_url}{endpoint}?{'&'.join(query_parts)}"


def save_raw(save_dir: Path, api_name: str, suffix: str, envelope: dict) -> Path:
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"raw_{api_name}_{TODAY}_{suffix}.json"
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def fallback_envelope(
    api_name: str,
    error_class: str,
    error_message: str,
    request_meta: dict,
    http_status: int | None = None,
    response_body: str = "",
) -> dict:
    mock_file = MOCK_FALLBACK_MAP.get(api_name)
    mock_body = None
    if mock_file and (MOCK_DIR / mock_file).exists():
        mock_body = json.loads((MOCK_DIR / mock_file).read_text(encoding="utf-8"))
    return {
        "api": api_name,
        "source_system": "mock",
        "requested_at": datetime.now(KST).isoformat(),
        "request": request_meta,
        "live_call_ok": False,
        "http_status": http_status,
        "response_body": response_body,
        "error_class": error_class,
        "error_message": error_message,
        "fallback_mock_file": mock_file,
        "response": mock_body,
        "note": "실 API 호출 실패로 가이드 5장 Fallback 정책에 따라 mock 데이터로 대체 저장. "
                "실제 서비스 배포 전 아웃바운드 네트워크가 열린 환경에서 재실행하여 교체 필요.",
    }


def live_envelope(api_name: str, http_status: int, body: str, request_meta: dict) -> dict:
    parsed: object = body
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        pass
    return {
        "api": api_name,
        "source_system": "api_live",
        "requested_at": datetime.now(KST).isoformat(),
        "request": request_meta,
        "live_call_ok": True,
        "http_status": http_status,
        "response": parsed,
    }


def codef_token_envelope(api_name: str, http_status: int, body: str, request_meta: dict) -> dict:
    token_meta: dict[str, object] = {"token_issued": False}
    try:
        parsed = json.loads(body)
        token_meta = {
            "token_issued": bool(parsed.get("access_token")),
            "token_type": parsed.get("token_type"),
            "expires_in": parsed.get("expires_in"),
            "scope": parsed.get("scope"),
        }
    except json.JSONDecodeError:
        token_meta = {"token_issued": "access_token" in body}
    return {
        "api": api_name,
        "source_system": "api_live",
        "requested_at": datetime.now(KST).isoformat(),
        "request": request_meta,
        "live_call_ok": True,
        "http_status": http_status,
        "token": token_meta,
        "note": "CODEF OAuth 토큰 값은 보안상 raw 파일에 저장하지 않고 실행 메모리에서만 사용한다.",
    }


def run_api(name: str, spec: dict, env: dict, conn_results: list) -> None:
    save_dir = DATA_ROOT / spec["raw_save_dir"]
    if spec.get("manual_config_required"):
        request_meta = {
            "provider": spec.get("provider"),
            "base_url": spec.get("base_url", ""),
            "endpoint": spec.get("endpoint", ""),
            "required_config": spec.get("required_config", []),
            "notes": spec.get("notes", ""),
        }
        reason = spec.get("manual_config_reason", "manual API configuration required")
        env_out = fallback_envelope(name, "manual_config_required", reason, request_meta)
        path = save_raw(save_dir, name, "mock_fallback", env_out)
        conn_results.append({"api": name, "ok": False,
                               "error_class": "manual_config_required",
                               "error_message": reason,
                               "saved_to": str(path.relative_to(ROOT)), "fallback": "mock"})
        print(f"[FALLBACK] {name}: manual_config_required -> {path.relative_to(ROOT)}")
        return

    env_key = spec.get("env_key")
    key_value = env.get(env_key, "") if env_key else ""

    if env_key and not key_value:
        conn_results.append({"api": name, "ok": False, "error_class": "missing_key",
                               "note": f"{env_key} 미설정"})
        print(f"[SKIP] {name}: {env_key} 없음")
        return

    base_url = env.get(spec.get("base_url_env_key", ""), spec.get("base_url", ""))
    endpoint = env.get(spec.get("endpoint_env_key", ""), spec.get("endpoint", ""))
    method = spec.get("method", "GET")
    key_param = None
    if spec.get("auth", "").startswith("confmKey"):
        key_param = "confmKey"
    elif spec.get("auth", "").startswith("serviceKey"):
        key_param = "serviceKey"
    elif spec.get("auth", "").startswith("crtfc_key"):
        key_param = "crtfc_key"

    extra = SAMPLE_PARAMS.get(name, {})
    request_meta = {"base_url": base_url, "endpoint": endpoint, "method": method,
                     "params": extra, "key_param": key_param, "key_masked": mask(key_value)}

    if method == "GET":
        url = build_url(base_url, endpoint, key_param, key_value, extra)
        result = http_call(url, "GET")
    else:  # business_status: POST JSON body
        url = f"{base_url}{endpoint}?{key_query_part('serviceKey', key_value)}"
        payload = json.dumps({"b_no": ["1248100998"]}).encode("utf-8")
        result = http_call(url, "POST", data=payload,
                            headers={"Content-Type": "application/json", "Accept": "application/json"})

    if result["ok"]:
        env_out = live_envelope(name, result["http_status"], result["body"], request_meta)
        path = save_raw(save_dir, name, "live", env_out)
        conn_results.append({"api": name, "ok": True, "http_status": result["http_status"],
                               "saved_to": str(path.relative_to(ROOT))})
        print(f"[LIVE OK] {name} -> {path.relative_to(ROOT)}")
    else:
        env_out = fallback_envelope(name, result.get("error_class", "unknown_error"),
                                      result.get("error_message", ""), request_meta,
                                      result.get("http_status"), result.get("body", ""))
        path = save_raw(save_dir, name, "mock_fallback", env_out)
        conn_results.append({"api": name, "ok": False, "http_status": result.get("http_status"),
                               "error_class": result.get("error_class"),
                               "error_message": result.get("error_message"),
                               "saved_to": str(path.relative_to(ROOT)), "fallback": "mock"})
        print(f"[FALLBACK] {name}: {result.get('error_class')} -> {path.relative_to(ROOT)}")


def run_codef(env: dict, conn_results: list) -> None:
    codef_env = env.get("CODEF_ENV", "sandbox").lower()
    prefix = "CODEF_DEMO" if codef_env == "demo" else "CODEF_SANDBOX"
    base = env.get(f"{prefix}_BASE_URL", "https://sandbox.codef.io")
    oauth_url = env.get("CODEF_OAUTH_URL", "https://oauth.codef.io/oauth/token")
    client_id = env.get(f"{prefix}_CLIENT_ID", "")
    client_secret = env.get(f"{prefix}_CLIENT_SECRET", "")
    request_meta = {"base_url": base, "oauth_url": oauth_url, "env": codef_env,
                     "client_id_masked": mask(client_id)}

    if not client_id or not client_secret:
        conn_results.append({"api": "codef_registry", "ok": False, "error_class": "missing_key"})
        print("[SKIP] codef_registry: credentials 없음")
        return

    import base64
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    result = http_call(oauth_url, "POST",
                        data=b"grant_type=client_credentials&scope=read",
                        headers={"Authorization": f"Basic {auth}",
                                  "Content-Type": "application/x-www-form-urlencoded"})

    save_dir = DATA_ROOT / "raw/codef"
    if result["ok"] and "access_token" in result["body"]:
        env_out = codef_token_envelope("codef_registry", result["http_status"], result["body"], request_meta)
        path = save_raw(save_dir, "codef_registry", "live_token", env_out)
        conn_results.append({"api": "codef_registry", "ok": True,
                               "http_status": result["http_status"],
                               "token_issued": True,
                               "saved_to": str(path.relative_to(ROOT))})
        print(f"[LIVE OK] codef_registry -> {path.relative_to(ROOT)}")
    else:
        env_out = fallback_envelope("codef_registry", result.get("error_class", "unknown_error"),
                                      result.get("error_message", result.get("body", "")[:200]), request_meta,
                                      result.get("http_status"), result.get("body", ""))
        path = save_raw(save_dir, "codef_registry", "mock_fallback", env_out)
        conn_results.append({"api": "codef_registry", "ok": False,
                               "http_status": result.get("http_status"),
                               "error_class": result.get("error_class"),
                               "error_message": result.get("error_message"),
                               "saved_to": str(path.relative_to(ROOT)), "fallback": "mock"})
        print(f"[FALLBACK] codef_registry: {result.get('error_class')} -> {path.relative_to(ROOT)}")


def main() -> int:
    env = load_env()
    if not env:
        print("ERROR: backend/.env 없음", file=sys.stderr)
        return 1

    endpoints = yaml.safe_load(ENDPOINTS_FILE.read_text(encoding="utf-8"))
    apis = endpoints["apis"]

    conn_results: list = [{
        "tested_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "purpose": env.get("APP_PURPOSE", ""),
        "run_context": "sandbox 실행 환경 (아웃바운드 네트워크가 허용 도메인 목록으로 제한될 수 있음). "
                        "network_blocked_* 로 표시된 항목은 로컬 PC 등 개방된 네트워크에서 재실행 필요.",
    }]

    order = endpoints.get("orchestration_order", list(apis.keys()))
    for name in order:
        if name == "codef":
            run_codef(env, conn_results)
            continue
        spec = apis.get(f"{name}_apt_trade") or apis.get(name) or apis.get(f"{name}_list") or apis.get(f"{name}_registry")
        # orchestration_order 이름과 apis 딕셔너리 키가 다른 항목 보정
        key_map = {
            "juso": "juso", "codef": "codef_registry", "building": "building_registry",
            "rtms": "rtms_apt_trade", "official_price": None, "business_status": "business_status",
            "dart": "dart_list",
        }
        real_key = key_map.get(name, name)
        if real_key is None:
            for oname in ["official_price_apt", "official_price_house", "official_price_land"]:
                run_api(oname, apis[oname], env, conn_results)
            continue
        if real_key in apis:
            run_api(real_key, apis[real_key], env, conn_results)

    METADATA.mkdir(parents=True, exist_ok=True)
    CONN_TEST_FILE.write_text(json.dumps(conn_results, ensure_ascii=False, indent=2), encoding="utf-8")

    live_count = sum(1 for r in conn_results if isinstance(r, dict) and r.get("ok"))
    total = sum(1 for r in conn_results if isinstance(r, dict) and "api" in r)
    print(f"\n실 호출 성공 {live_count}/{total}, 나머지는 mock fallback으로 raw/ 저장 완료")
    print(f"연결 테스트 결과: {CONN_TEST_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
