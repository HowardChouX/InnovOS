"""
Middleware tests — verify security headers, request ID, error handling.
"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.fixture
def middleware_app():
    """A minimal FastAPI app with all middleware for testing."""
    from app.middleware import (
        RequestIDMiddleware,
        SecurityHeadersMiddleware,
        GlobalExceptionHandler,
    )

    app = FastAPI()

    @app.get("/api/test")
    def test_route():
        return {"ok": True}

    @app.get("/api/error")
    def error_route():
        raise ValueError("test error")

    @app.get("/api/http-error")
    def http_error_route():
        raise HTTPException(status_code=400, detail="bad request")

    app.add_middleware(GlobalExceptionHandler)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    return app


@pytest.fixture
def client(middleware_app):
    return TestClient(middleware_app)


class TestSecurityHeaders:
    """安全响应头测试"""

    def test_security_headers_present(self, client):
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("x-xss-protection") == "1; mode=block"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers.get("permissions-policy", "")
        assert "default-src 'self'" in resp.headers.get("content-security-policy", "")

    def test_no_cache_on_api(self, client):
        resp = client.get("/api/test")
        assert "no-store" in resp.headers.get("cache-control", "")

    def test_skip_hsts_on_localhost(self, client):
        """本地开发环境不启用 HSTS"""
        resp = client.get("/api/test", headers={"host": "localhost:8000"})
        # HSTS header should not be present (or be the default)
        hsts = resp.headers.get("strict-transport-security", "")
        assert hsts == "" or "max-age=0" in hsts


class TestRequestID:
    """请求 ID 测试"""

    def test_request_id_generated(self, client):
        resp = client.get("/api/test")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) > 0

    def test_request_id_propagated(self, client):
        """客户端提供的 X-Request-ID 应被透传"""
        resp = client.get("/api/test", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers.get("x-request-id") == "my-custom-id"


class TestGlobalExceptionHandler:
    """全局异常处理器测试"""

    def test_unhandled_exception(self, client):
        resp = client.get("/api/error")
        assert resp.status_code == 500
        data = resp.json()
        assert "detail" in data
        assert "requestId" in data
        assert "服务器内部错误" in data["detail"]

    def test_http_exception_passthrough(self, client):
        """HTTPException 应该被正常处理（不经过全局异常处理器）"""
        resp = client.get("/api/http-error")
        assert resp.status_code == 400
        data = resp.json()
        assert data["detail"] == "bad request"
