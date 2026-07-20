#!/usr/bin/env python3
"""Generate OpenAI embeddings for MongoDB rag_chunks and create a vector index."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import certifi
from openai import OpenAI
from pymongo import MongoClient, UpdateOne
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
from pymongo.operations import SearchIndexModel

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
            env[key.strip()] = value.strip().strip('"').strip("'")
        if env:
            return env
    return env


def require(env: dict[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise SystemExit(f"Missing required setting: {key}")
    return value


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunks(items: list[dict], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def select_pending(collection, model: str, dimensions: int, force: bool) -> list[dict]:
    projection = {
        "_id": 1,
        "chunk_id": 1,
        "text": 1,
        "embedding": 1,
        "embedding_model": 1,
        "embedding_dimensions": 1,
        "embedding_source_hash": 1,
    }
    pending: list[dict] = []
    for doc in collection.find({}, projection).sort("chunk_id", 1):
        text = (doc.get("text") or "").strip()
        if not text:
            continue
        source_hash = text_hash(text)
        is_current = (
            isinstance(doc.get("embedding"), list)
            and len(doc["embedding"]) == dimensions
            and doc.get("embedding_model") == model
            and doc.get("embedding_dimensions") == dimensions
            and doc.get("embedding_source_hash") == source_hash
        )
        if force or not is_current:
            doc["text"] = text
            doc["source_hash"] = source_hash
            pending.append(doc)
    return pending


def embed_pending(collection, client: OpenAI, pending: list[dict], model: str, dimensions: int, batch_size: int) -> tuple[int, int]:
    embedded = 0
    total_tokens = 0
    total_batches = (len(pending) + batch_size - 1) // batch_size
    for batch_number, batch in enumerate(chunks(pending, batch_size), start=1):
        response = client.embeddings.create(
            model=model,
            input=[doc["text"] for doc in batch],
            dimensions=dimensions,
            encoding_format="float",
        )
        vectors = sorted(response.data, key=lambda item: item.index)
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding response count does not match request count")

        now = datetime.now(timezone.utc)
        operations = []
        for doc, result in zip(batch, vectors):
            operations.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "embedding": result.embedding,
                            "embedding_model": model,
                            "embedding_dimensions": dimensions,
                            "embedding_source_hash": doc["source_hash"],
                            "embedded_at": now,
                            "updated_at": now,
                        }
                    },
                )
            )
        collection.bulk_write(operations, ordered=False)
        embedded += len(batch)
        total_tokens += response.usage.total_tokens
        print(f"[EMBED] batch {batch_number}/{total_batches}: {embedded}/{len(pending)} chunks")
    return embedded, total_tokens


def ensure_vector_index(collection, name: str, dimensions: int) -> str:
    definition = {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": dimensions,
                "similarity": "cosine",
            },
            {"type": "filter", "path": "topic"},
            {"type": "filter", "path": "region_sido"},
            {"type": "filter", "path": "region_sigungu"},
        ]
    }
    existing = {item.get("name"): item for item in collection.list_search_indexes()}
    if name in existing:
        collection.update_search_index(name, definition)
        return "updated"

    model = SearchIndexModel(
        definition=definition,
        name=name,
        type="vectorSearch",
    )
    collection.create_search_index(model=model)
    return "created"


def wait_for_index(collection, name: str, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_status = "pending"
    while time.monotonic() < deadline:
        indexes = list(collection.list_search_indexes(name))
        if indexes:
            index = indexes[0]
            last_status = str(index.get("status", "unknown"))
            if index.get("queryable") is True or last_status.upper() == "READY":
                return "ready"
            if last_status.upper() in {"FAILED", "DELETING"}:
                return last_status.lower()
        time.sleep(5)
    return last_status.lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Regenerate all embeddings")
    parser.add_argument("--skip-index", action="store_true", help="Do not create/update the Atlas Vector Search index")
    parser.add_argument("--limit", type=int, default=0, help="Embed at most N pending chunks")
    parser.add_argument("--wait-seconds", type=int, default=180, help="Maximum index readiness wait")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = load_env()
    uri = require(env, "MONGODB_URI")
    db_name = require(env, "MONGODB_DB_NAME")
    api_key = env.get("OPENAI_API_KEY", "").strip() or env.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Missing required setting: OPENAI_API_KEY")

    model = env.get("EMBEDDING_MODEL_NAME", "text-embedding-3-large").strip()
    dimensions = int(env.get("EMBEDDING_DIMENSIONS", "1024"))
    batch_size = int(env.get("EMBEDDING_BATCH_SIZE", "64"))
    index_name = env.get("MONGODB_VECTOR_INDEX", "rag_chunks_vector_index").strip()

    mongo = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=15000)
    try:
        mongo.admin.command("ping")
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
    collection = mongo[db_name].rag_chunks
    pending = select_pending(collection, model, dimensions, args.force)
    if args.limit > 0:
        pending = pending[: args.limit]

    print(f"[CONFIG] database={db_name}, model={model}, dimensions={dimensions}")
    print(f"[PLAN] pending={len(pending)}, total={collection.count_documents({})}")

    embedded = 0
    total_tokens = 0
    if pending:
        openai_client = OpenAI(api_key=api_key, timeout=60.0, max_retries=4)
        embedded, total_tokens = embed_pending(
            collection, openai_client, pending, model, dimensions, batch_size
        )

    index_status = "skipped"
    if not args.skip_index:
        try:
            action = ensure_vector_index(collection, index_name, dimensions)
            index_status = wait_for_index(collection, index_name, args.wait_seconds)
            print(f"[INDEX] {action}: {index_name}, status={index_status}")
        except OperationFailure as exc:
            print(f"[INDEX ERROR] {exc}", file=sys.stderr)
            return 2

    ready = collection.count_documents(
        {
            "embedding_model": model,
            "embedding_dimensions": dimensions,
            f"embedding.{dimensions - 1}": {"$exists": True},
        }
    )
    print(f"[DONE] embedded={embedded}, ready={ready}, input_tokens={total_tokens}, index={index_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
