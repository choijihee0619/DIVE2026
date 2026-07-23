#!/usr/bin/env python3
"""고정 S1~S7 HUG 업무흐름 시연 Seed를 MongoDB에 upsert한다.

실행::

    cd backend
    .venv/bin/python scripts/seed_hug_workflow.py
    .venv/bin/python scripts/seed_hug_workflow.py --cached-predictions
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.demo_scenario_service import DemoScenarioService  # noqa: E402


async def _run(use_model: bool) -> int:
    settings = get_settings()
    if not settings.mongodb_uri:
        print("ERROR: MONGODB_URI가 설정되지 않았습니다.", file=sys.stderr)
        return 1
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=15000,
    )
    try:
        manifest = await DemoScenarioService(client[settings.mongodb_db_name]).seed(
            use_model=use_model
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="HUG S1~S7 고정 시연 Seed")
    parser.add_argument(
        "--cached-predictions",
        action="store_true",
        help="저장 모델 대신 명시적 cached_demo_prediction을 사용",
    )
    args = parser.parse_args()
    return asyncio.run(_run(use_model=not args.cached_predictions))


if __name__ == "__main__":
    raise SystemExit(main())

