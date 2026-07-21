"""CODEF 응답 구조 파악용 임시 스크립트 (확인 후 삭제 예정)."""
import asyncio
import json
import sys

sys.path.insert(0, ".")

from app.services import codef_client


async def main() -> None:
    body = await codef_client.fetch_register("서울특별시 마포구 월드컵로 120")
    data = body.get("data", {})
    print("data keys:", list(data.keys()))
    entries = data.get("resRegisterEntriesList", [])
    print("entries:", len(entries))
    e = entries[0]
    print("entry keys:", list(e.keys()))
    for his in e.get("resRegistrationHisList", []):
        print("\n== resType:", his.get("resType"), "| resType1:", his.get("resType1"), "| keys:", list(his.keys()))
        contents = his.get("resContentsList", [])
        print("   contents:", len(contents))
        for c in contents[:3]:
            print("   content keys:", list(c.keys()), "resType2:", c.get("resType2"))
            for d in c.get("resDetailList", [])[:8]:
                print("      detail:", json.dumps(d, ensure_ascii=False)[:160])


asyncio.run(main())
