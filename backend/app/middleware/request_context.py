"""Request-ID/Trace-ID 처리 미들웨어.

API_Contract_260714.yaml 10.2절: 요청 헤더는 `Request-ID`/`Trace-ID`(X- 접두어 없음),
응답 헤더는 `X-Request-ID`/`X-Trace-ID`(X- 접두어 있음)로 이름이 다르다(부록H #1, 계약 원문 그대로 구현).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.utils.datetime_utils import new_request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("Request-ID") or new_request_id()
        trace_id = request.headers.get("Trace-ID")

        request.state.request_id = request_id
        request.state.trace_id = trace_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        return response
