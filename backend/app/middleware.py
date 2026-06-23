"""
Enterprise middleware: security headers, request ID, rate limiting, global error handler.
"""

import logging
import time
import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

_ENV = settings.ENVIRONMENT


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求分配唯一 ID (X-Request-ID)，透传客户端提供的值。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加企业级安全响应头。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # 静默健康检查探针，不额外增加头（已是最小响应）
        if request.url.path == "/api/health":
            return response

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS — 仅非 localhost 时启用
        host = request.headers.get("host", "")
        if "localhost" not in host and "127.0.0.1" not in host:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # CSP — 后端 API 仅返回 JSON，script-src/style-src 对 API 响应影响有限。
        # 前端 SPA 的 CSP 由 nginx.conf 管理。
        # connect-src 限制 API 可发起的 fetch/XHR 目标。
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # API 路由不缓存
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """结构化请求日志：方法、路径、状态码、耗时、请求ID。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 1)
        req_id = getattr(request.state, "request_id", "-")
        logger.info(
            "request_log",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else "-",
            },
        )
        return response


class GlobalExceptionHandler(BaseHTTPMiddleware):
    """Global exception handler — sanitizes errors in production."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            raise  # Let FastAPI handle HTTPExceptions normally
        except Exception as exc:
            logger.exception(
                "Unhandled exception (request_id=%s): %s",
                request.state.request_id,
                exc,
            )
            detail = "服务器内部错误"
            if _ENV != "production":
                detail = f"{detail}: {type(exc).__name__}: {exc}"
            return JSONResponse(
                status_code=500,
                content={"detail": detail, "requestId": request.state.request_id},
            )
