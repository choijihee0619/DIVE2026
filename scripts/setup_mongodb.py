#!/usr/bin/env python3
"""
MongoDB Atlas 초기 설정 및 해커톤 개발용 데이터 시드.

동작:
  1. backend/.env 에서 MONGODB_URI, MONGODB_DB_NAME 을 읽는다.
  2. 핵심 컬렉션과 인덱스를 생성한다.
  3. 현재 workspace의 raw/mock/RAG 산출물을 MongoDB에 idempotent upsert 한다.

주의:
  - 실제 계약서/PDF 원문은 MongoDB에 넣지 않는다.
  - CODEF OAuth 토큰 원문은 저장하지 않는다.
  - RAG chunk는 embedding 없이 먼저 적재한다. embedding은 모델 확정 후 별도 생성한다.
"""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from pymongo import ASCENDING, DESCENDING, MongoClient, TEXT
from pymongo.errors import CollectionInvalid, OperationFailure

try:
    import certifi
except ImportError:
    CERTIFI_CA_FILE = None
else:
    CERTIFI_CA_FILE = certifi.where()

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DATA_ROOT = ROOT / "개별수집데이터 및 API"
RAW = DATA_ROOT / "raw"
MOCK = DATA_ROOT / "mock"
PROCESSED = DATA_ROOT / "processed"
METADATA = DATA_ROOT / "metadata"

NOW = datetime.now(timezone.utc)
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "dive2026-hug-anshim")


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
            env[key.strip()] = value.strip().strip('"').strip("'")
        if env:
            return env
    return env


def stable_id(*parts: object) -> str:
    return str(uuid.uuid5(NAMESPACE, "::".join(str(p) for p in parts)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_json(pattern: str) -> Path | None:
    files = sorted(ROOT.glob(pattern))
    return files[-1] if files else None


def ensure_collections(db) -> None:
    collections = [
        "users",
        "properties",
        "contracts",
        "contract_versions",
        "registry_snapshots",
        "building_registry_snapshots",
        "rtms_transactions",
        "official_price_snapshots",
        "landlords",
        "risk_assessments",
        "evidence_requests",
        "evidences",
        "verifications",
        "return_plans",
        "incidents",
        "recovery_predictions",
        "timeline_events",
        "blockchain_transactions",
        "notifications",
        "counsels",
        "referrals",
        "api_call_logs",
        "api_raw_snapshots",
        "system_logs",
        "model_versions",
        "data_sources",
        "rag_chunks",
        "llm_conversations",
        "llm_messages",
        "llm_answer_logs",
        "schema_migrations",
    ]
    existing = set(db.list_collection_names())
    for name in collections:
        if name not in existing:
            try:
                db.create_collection(name)
            except CollectionInvalid:
                pass


def create_indexes(db) -> None:
    def safe_index(collection: str, keys, **kwargs) -> None:
        try:
            db[collection].create_index(keys, **kwargs)
        except OperationFailure as exc:
            print(f"[WARN] index skipped {collection}: {exc}", file=sys.stderr)

    safe_index("users", [("email", ASCENDING)], unique=True, sparse=True)
    safe_index("users", [("role", ASCENDING)])

    safe_index("properties", [("address.road_address", ASCENDING)])
    safe_index("properties", [("address.adm_cd", ASCENDING)])
    safe_index("properties", [("address.bd_mgt_sn", ASCENDING)], sparse=True)

    safe_index("contracts", [("property_id", ASCENDING)])
    safe_index("contracts", [("tenant_user_id", ASCENDING)])
    safe_index("contracts", [("landlord_user_id", ASCENDING)], sparse=True)
    safe_index("contracts", [("contract_status", ASCENDING)])
    safe_index("contracts", [("contract_end_date", ASCENDING)])

    safe_index("registry_snapshots", [("property_id", ASCENDING)])
    safe_index("registry_snapshots", [("source_system", ASCENDING)])
    safe_index("building_registry_snapshots", [("property_id", ASCENDING)])
    safe_index("rtms_transactions", [("lawd_cd", ASCENDING), ("deal_ymd", DESCENDING)])
    safe_index("official_price_snapshots", [("property_id", ASCENDING)])
    safe_index("official_price_snapshots", [("price_type", ASCENDING), ("base_year", DESCENDING)])

    safe_index("risk_assessments", [("case_id", ASCENDING)], unique=True, sparse=True)
    safe_index("risk_assessments", [("contract_id", ASCENDING)], sparse=True)
    safe_index("risk_assessments", [("risk_grade", ASCENDING)])

    safe_index("api_call_logs", [("api_name", ASCENDING), ("called_at", DESCENDING)])
    safe_index("api_raw_snapshots", [("api", ASCENDING), ("requested_at", DESCENDING)])
    safe_index("timeline_events", [("contract_id", ASCENDING), ("created_at", DESCENDING)])
    safe_index("blockchain_transactions", [("event_type", ASCENDING), ("reference_id", ASCENDING)], unique=True, sparse=True)
    safe_index("blockchain_transactions", [("tx_hash", ASCENDING)], unique=True, sparse=True)

    safe_index("rag_chunks", [("chunk_id", ASCENDING)], unique=True)
    safe_index("rag_chunks", [("doc_id", ASCENDING)])
    safe_index("rag_chunks", [("topic", ASCENDING)])
    safe_index("rag_chunks", [("region_sido", ASCENDING), ("region_sigungu", ASCENDING)])
    safe_index("rag_chunks", [("text", TEXT)])

    safe_index("llm_conversations", [("contract_id", ASCENDING)], sparse=True)
    safe_index("llm_messages", [("conversation_id", ASCENDING), ("created_at", ASCENDING)])
    safe_index("llm_answer_logs", [("conversation_id", ASCENDING), ("created_at", DESCENDING)])


def seed_data_sources(db) -> int:
    candidates = []
    for rel in [
        "metadata/api_connection_test_260714.json",
        "metadata/api_endpoints_260714.yaml",
        "metadata/API_등록_현황_260714.md",
        "metadata/API_키_신청_체크리스트_260714.md",
        "processed/rag/rag_chunks_260714_reviewed.jsonl",
        "processed/ml/README.md",
    ]:
        path = DATA_ROOT / rel
        if path.exists():
            candidates.append(path)
    candidates.extend(sorted((DATA_ROOT / "raw").glob("*/*20260715*.json")))
    candidates.extend(sorted(MOCK.glob("*.json")))

    count = 0
    for path in candidates:
        rel = str(path.relative_to(ROOT))
        doc = {
            "_id": stable_id("data_source", rel),
            "path": rel,
            "file_name": path.name,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "source_group": path.parts[-3] if len(path.parts) >= 3 else "",
            "created_at": NOW,
            "updated_at": NOW,
        }
        db.data_sources.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        count += 1
    return count


def seed_api_call_logs(db) -> int:
    path = METADATA / "api_connection_test_260714.json"
    if not path.exists():
        return 0
    rows = json.loads(path.read_text(encoding="utf-8"))
    tested_at = rows[0].get("tested_at") if rows and isinstance(rows[0], dict) else ""
    count = 0
    for row in rows[1:]:
        if not isinstance(row, dict) or not row.get("api"):
            continue
        doc = {
            "_id": stable_id("api_call_log", tested_at, row.get("api")),
            "api_name": row.get("api"),
            "called_at_label": tested_at,
            "called_at": NOW,
            "http_status": row.get("http_status"),
            "ok": bool(row.get("ok")),
            "api_result_status": "Success" if row.get("ok") else "MockFallback",
            "error_class": row.get("error_class"),
            "error_message": row.get("error_message"),
            "saved_to": row.get("saved_to"),
            "fallback_used": bool(row.get("fallback")),
            "created_at": NOW,
            "updated_at": NOW,
        }
        db.api_call_logs.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        count += 1
    return count


def seed_raw_snapshots(db) -> int:
    count = 0
    for path in sorted(RAW.glob("*/*20260715*.json")):
        data = read_json(path)
        rel = str(path.relative_to(ROOT))
        doc = {
            "_id": stable_id("api_raw_snapshot", rel),
            "api": data.get("api"),
            "source_system": data.get("source_system"),
            "live_call_ok": data.get("live_call_ok"),
            "http_status": data.get("http_status"),
            "error_class": data.get("error_class"),
            "error_message": data.get("error_message"),
            "requested_at": data.get("requested_at"),
            "request": data.get("request"),
            "response": data.get("response"),
            "response_body": data.get("response_body"),
            "raw_path": rel,
            "raw_sha256": sha256_file(path),
            "created_at": NOW,
            "updated_at": NOW,
        }
        db.api_raw_snapshots.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        count += 1
    return count


def seed_mock_registry(db) -> int:
    count = 0
    for path in sorted(MOCK.glob("mock_registry_*.json")):
        data = read_json(path)
        address = data.get("address", {})
        property_id = stable_id("property", address.get("road_address") or path.stem)
        db.properties.update_one(
            {"_id": property_id},
            {"$set": {
                "_id": property_id,
                "address": {
                    "road_address": address.get("road_address"),
                    "adm_cd": address.get("adm_cd"),
                },
                "source_system": "mock",
                "created_at": NOW,
                "updated_at": NOW,
            }},
            upsert=True,
        )
        doc = {
            "_id": stable_id("registry_snapshot", path.stem),
            "property_id": property_id,
            "api_result_status": "MockFallback",
            "source": data.get("source", path.stem),
            "source_system": "mock",
            "rights_summary": data.get("registry"),
            "features": data.get("features"),
            "label": data.get("label"),
            "raw": data,
            "fetched_at": NOW,
            "created_at": NOW,
            "updated_at": NOW,
        }
        db.registry_snapshots.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        count += 1
    return count


def seed_official_price_mock(db) -> int:
    path = MOCK / "mock_official_price_success.json"
    if not path.exists():
        return 0
    data = read_json(path)
    property_id = stable_id("property", data.get("address", {}).get("road_address"), data.get("complex_name"))
    db.properties.update_one(
        {"_id": property_id},
        {"$set": {
            "_id": property_id,
            "address": data.get("address", {}),
            "housing_type": "apartment",
            "source_system": "mock",
            "created_at": NOW,
            "updated_at": NOW,
        }},
        upsert=True,
    )
    count = 0
    for price_type in ["apt", "house", "land"]:
        doc = {
            "_id": stable_id("official_price", price_type, data.get("case_id")),
            "property_id": property_id,
            "price_type": price_type,
            "source_system": "mock",
            "official_price": data.get("official_price"),
            "base_year": data.get("base_year"),
            "address": data.get("address"),
            "complex_name": data.get("complex_name"),
            "dong": data.get("dong"),
            "ho": data.get("ho"),
            "exclusive_area_sqm": data.get("exclusive_area_sqm"),
            "raw": data,
            "created_at": NOW,
            "updated_at": NOW,
        }
        db.official_price_snapshots.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        count += 1
    return count


def seed_building_snapshot(db) -> int:
    files = sorted((RAW / "building").glob("raw_building_registry_*_live.json"))
    path = files[-1] if files else None
    if not path:
        return 0
    data = read_json(path)
    req = data.get("request", {})
    params = req.get("params", {})
    property_id = stable_id("property", "building", params.get("sigunguCd"), params.get("bjdongCd"), params.get("bun"), params.get("ji"))
    db.properties.update_one(
        {"_id": property_id},
        {"$set": {
            "_id": property_id,
            "address": {
                "adm_cd": f"{params.get('sigunguCd', '')}{params.get('bjdongCd', '')}",
                "bun": params.get("bun"),
                "ji": params.get("ji"),
            },
            "source_system": data.get("source_system"),
            "created_at": NOW,
            "updated_at": NOW,
        }},
        upsert=True,
    )
    doc = {
        "_id": stable_id("building_registry_snapshot", str(path.relative_to(ROOT))),
        "property_id": property_id,
        "source_system": data.get("source_system"),
        "http_status": data.get("http_status"),
        "request": req,
        "response": data.get("response"),
        "raw_path": str(path.relative_to(ROOT)),
        "created_at": NOW,
        "updated_at": NOW,
    }
    db.building_registry_snapshots.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
    return 1


def seed_rtms_transaction(db) -> int:
    files = sorted((RAW / "rtms").glob("raw_rtms_apt_trade_*_live.json"))
    path = files[-1] if files else None
    if not path:
        return 0
    data = read_json(path)
    response = data.get("response") or ""
    parsed: dict[str, Any] = {}
    try:
        root = ElementTree.fromstring(response)
        item = root.find(".//item")
        if item is not None:
            parsed = {child.tag: (child.text or "").strip() for child in item}
    except ElementTree.ParseError:
        parsed = {}
    req = data.get("request", {})
    params = req.get("params", {})
    doc = {
        "_id": stable_id("rtms_transaction", str(path.relative_to(ROOT)), parsed.get("aptNm"), parsed.get("dealYear"), parsed.get("dealMonth"), parsed.get("dealDay")),
        "source_system": data.get("source_system"),
        "lawd_cd": params.get("LAWD_CD") or parsed.get("sggCd"),
        "deal_ymd": params.get("DEAL_YMD"),
        "apt_name": parsed.get("aptNm"),
        "umd_name": parsed.get("umdNm"),
        "jibun": parsed.get("jibun"),
        "deal_amount_raw": parsed.get("dealAmount"),
        "exclusive_area_sqm": float(parsed["excluUseAr"]) if parsed.get("excluUseAr") else None,
        "floor": int(parsed["floor"]) if parsed.get("floor") and parsed["floor"].lstrip("-").isdigit() else None,
        "build_year": int(parsed["buildYear"]) if parsed.get("buildYear") and parsed["buildYear"].isdigit() else None,
        "raw_item": parsed,
        "request": req,
        "raw_path": str(path.relative_to(ROOT)),
        "created_at": NOW,
        "updated_at": NOW,
    }
    db.rtms_transactions.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
    return 1


def seed_rag_chunks(db) -> int:
    path = PROCESSED / "rag" / "rag_chunks_260714_reviewed.jsonl"
    if not path.exists():
        return 0
    count = 0
    batch = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            doc = {
                "_id": stable_id("rag_chunk", row.get("chunk_id")),
                "chunk_id": row.get("chunk_id"),
                "doc_id": row.get("doc_id"),
                "source": row.get("source"),
                "topic": row.get("topic"),
                "consultation_stage": row.get("consultation_stage"),
                "region_sido": row.get("region_sido"),
                "region_sigungu": row.get("region_sigungu"),
                "region_code": row.get("region_code"),
                "text": row.get("text"),
                "metadata": row.get("metadata", {}),
                "created_at": NOW,
                "updated_at": NOW,
            }
            batch.append(doc)
            if len(batch) >= 500:
                for item in batch:
                    db.rag_chunks.update_one(
                        {"chunk_id": item["chunk_id"]},
                        {
                            "$set": item,
                            "$setOnInsert": {
                                "embedding": None,
                                "embedding_model": None,
                                "embedding_dimensions": None,
                            },
                        },
                        upsert=True,
                    )
                    count += 1
                batch = []
    for item in batch:
        db.rag_chunks.update_one(
            {"chunk_id": item["chunk_id"]},
            {
                "$set": item,
                "$setOnInsert": {
                    "embedding": None,
                    "embedding_model": None,
                    "embedding_dimensions": None,
                },
            },
            upsert=True,
        )
        count += 1
    return count


def seed_schema_version(db) -> None:
    doc = {
        "_id": "mongo_setup_20260715_v1",
        "name": "mongo_setup",
        "version": 1,
        "description": "Initial Atlas collections, indexes, raw/mock/RAG seed for DIVE2026",
        "applied_at": NOW,
    }
    db.schema_migrations.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)


def main() -> int:
    env = load_env()
    uri = env.get("MONGODB_URI")
    db_name = env.get("MONGODB_DB_NAME")
    if not uri or not db_name:
        print("ERROR: MONGODB_URI and MONGODB_DB_NAME are required in backend/.env", file=sys.stderr)
        return 1
    if db_name.endswith(".mongodb.net"):
        print("ERROR: MONGODB_DB_NAME must be a database name such as 'dive2026', not an Atlas host.", file=sys.stderr)
        return 1

    client_kwargs = {"serverSelectionTimeoutMS": 15000}
    if CERTIFI_CA_FILE:
        client_kwargs["tlsCAFile"] = CERTIFI_CA_FILE
    client = MongoClient(uri, **client_kwargs)
    client.admin.command("ping")
    db = client[db_name]

    ensure_collections(db)
    create_indexes(db)
    seed_schema_version(db)

    counts = {
        "data_sources": seed_data_sources(db),
        "api_call_logs": seed_api_call_logs(db),
        "api_raw_snapshots": seed_raw_snapshots(db),
        "registry_snapshots": seed_mock_registry(db),
        "official_price_snapshots": seed_official_price_mock(db),
        "building_registry_snapshots": seed_building_snapshot(db),
        "rtms_transactions": seed_rtms_transaction(db),
        "rag_chunks": seed_rag_chunks(db),
    }

    print(f"MongoDB setup complete: database={db_name}")
    for key, value in counts.items():
        print(f"- {key}: upserted {value}")
    print(f"- collections: {len(db.list_collection_names())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
