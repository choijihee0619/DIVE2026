from __future__ import annotations


async def test_openapi_schema_available(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"].startswith("HUG")

    bearer = schema["components"]["securitySchemes"]["BearerAuth"]
    assert bearer["type"] == "http"
    assert bearer["scheme"] == "bearer"
    assert bearer["bearerFormat"] == "JWT"


async def test_swagger_docs_available(client):
    resp = await client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()
