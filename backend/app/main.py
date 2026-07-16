"""FastAPI 앱 엔트리포인트.

lifespan에서 MongoDB 연결/인덱스 보장을 수행하고 종료 시 연결을 닫는다. 공통 예외 처리,
CORS, Request-ID/Trace-ID 미들웨어, `/health`·`/api/v1/health`, Swagger(`/docs`)를 구성한다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import health as health_endpoint
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.responses import error_response
from app.db.indexes import ensure_indexes
from app.db.mongodb import MongoDB
from app.middleware.request_context import RequestContextMiddleware

settings = get_settings()
configure_logging(settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await MongoDB.connect()
    await ensure_indexes(MongoDB.db)
    logger.info("Startup complete: %s (%s)", settings.app_name, settings.app_env)
    yield
    await MongoDB.close()


app = FastAPI(
    title="HUG 안심전세 체인 Backend",
    description="HUG × 아이엔 안심전세 체인 API_Contract_260714.yaml 기반 FastAPI MVP 백엔드",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Trace-ID", "X-Model-Version", "X-Blockchain-Version"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    request_id = getattr(request.state, "request_id", "req_unknown")
    logger.warning("AppError %s: %s", exc.error_code, exc.message)
    return error_response(exc.error_code, exc.message, request_id, exc.http_status, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "req_unknown")
    field_errors = [{"field": ".".join(str(p) for p in e["loc"]), "reason": e["msg"]} for e in exc.errors()]
    return error_response(
        "ERROR-002", "요청 값 검증에 실패했습니다.", request_id, 422, {"field_errors": field_errors}
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "req_unknown")
    logger.exception("Unhandled error: %s", exc)
    return error_response("ERROR-001", "예상하지 못한 서버 오류가 발생했습니다.", request_id, 500)


# `/health`(루트)와 `/api/v1/health`를 동시에 노출한다(과제 완료조건 항목).
app.include_router(health_endpoint.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)
