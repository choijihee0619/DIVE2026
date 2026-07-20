#!/usr/bin/env python3
"""임의의 RAG 청크 jsonl을 MongoDB dive2026.rag_chunks에 업서트.

사용: backend/.venv/bin/python scripts/load_rag_jsonl.py <jsonl 경로>
업서트 후 scripts/embed_rag_chunks.py를 실행하면 임베딩 없는 청크만 임베딩된다.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import certifi
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


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
            env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


def stable_id(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"파일 없음: {path}")
        return 1

    env = load_env()
    uri = env.get("MONGODB_URI") or env.get("MONGO_URI")
    if not uri:
        print("MONGODB_URI가 backend/.env에 없음")
        return 1
    db_name = env.get("MONGODB_DB_NAME") or env.get("MONGODB_DB") or "dive2026"
    client = MongoClient(
        uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=15_000,
    )
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError as exc:
        print("MongoDB Atlas 연결 실패.", file=sys.stderr)
        print(
            "Atlas의 Security > Network Access에서 현재 공인 IP를 허용하고, "
            "클러스터가 실행 중인지 확인하세요.",
            file=sys.stderr,
        )
        print(
            "또한 방화벽에서 Atlas 호스트의 TCP 27017 아웃바운드 연결이 "
            "허용되어야 합니다.",
            file=sys.stderr,
        )
        print(f"원본 오류: {exc}", file=sys.stderr)
        return 2
    db = client[db_name]
    now = datetime.now(timezone.utc)

    count = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            doc = {
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
                "updated_at": now,
            }
            db.rag_chunks.update_one(
                {"chunk_id": doc["chunk_id"]},
                {
                    "$set": doc,
                    "$setOnInsert": {
                        "_id": stable_id("rag_chunk", row.get("chunk_id")),
                        "embedding": None,
                        "embedding_model": None,
                        "embedding_dimensions": None,
                        "created_at": now,
                    },
                },
                upsert=True,
            )
            count += 1
    total = db.rag_chunks.count_documents({})
    by_source = list(db.rag_chunks.aggregate([{"$group": {"_id": "$source", "n": {"$sum": 1}}}]))
    print(f"업서트 {count}건 완료. rag_chunks 총 {total}건, source별: {by_source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
