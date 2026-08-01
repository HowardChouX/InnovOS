"""Tests for app.algorithm.reachability_probe — Python port of cc-switch stream_check.rs."""
from __future__ import annotations

import time

import httpx
import pytest

from app.algorithm.reachability_probe import (
    DEFAULT_DEGRADED_THRESHOLD_MS,
    DEFAULT_TIMEOUT_SECS,
    MAX_TIMEOUT_SECS,
    MIN_TIMEOUT_SECS,
    ProbeConfig,
    probe_reachability,
    result_to_dict,
)


def _make_transport(responses: list[httpx.Response | Exception]) -> httpx.MockTransport:
    """按顺序消费 responses — 模拟多次重试场景。"""
    it = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            item = next(it)
        except StopIteration as exc:
            raise AssertionError(
                "MockTransport called more times than expected"
            ) from exc
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.MockTransport(handler)


# ═══════════════════════════════════════════════════════════════════════════
#  ProbeConfig
# ═══════════════════════════════════════════════════════════════════════════


class TestProbeConfig:
    def test_defaults(self):
        cfg = ProbeConfig()
        assert cfg.timeout_secs == DEFAULT_TIMEOUT_SECS
        assert cfg.degraded_threshold_ms == DEFAULT_DEGRADED_THRESHOLD_MS
        assert cfg.max_retries == 1
        assert cfg.user_agent is None

    def test_timeout_clamped_too_low(self):
        cfg = ProbeConfig.from_raw(timeout_secs=0.5)
        assert cfg.timeout_secs == MIN_TIMEOUT_SECS

    def test_timeout_clamped_too_high(self):
        cfg = ProbeConfig.from_raw(timeout_secs=999)
        assert cfg.timeout_secs == MAX_TIMEOUT_SECS

    def test_timeout_within_range_kept(self):
        cfg = ProbeConfig.from_raw(timeout_secs=10)
        assert cfg.timeout_secs == 10

    def test_max_retries_negative_clamps_to_zero(self):
        cfg = ProbeConfig.from_raw(max_retries=-3)
        assert cfg.max_retries == 0

    def test_user_agent_empty_string_becomes_none(self):
        cfg = ProbeConfig.from_raw(user_agent="")
        assert cfg.user_agent is None


# ═══════════════════════════════════════════════════════════════════════════
#  probe_reachability
# ═══════════════════════════════════════════════════════════════════════════


class TestProbeReachability:
    @pytest.mark.asyncio
    async def test_2xx_returns_operational(self):
        transport = _make_transport([httpx.Response(200, content=b"")])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://example.com", client=client
            )
        assert result.status == "ok"
        assert result.health == "operational"
        assert result.success is True
        assert result.http_status == 200
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_4xx_5xx_still_ok_for_reachability(self):
        """cc-switch 原则:任何 HTTP 响应都算可达(网关/端口活着)。"""
        for status in (401, 403, 404, 429, 500, 502, 503):
            transport = _make_transport([httpx.Response(status, content=b"")])
            async with httpx.AsyncClient(transport=transport) as client:
                result = await probe_reachability(
                    "https://example.com", client=client
                )
            assert result.status == "ok"
            assert result.success is True
            assert result.http_status == status

    @pytest.mark.asyncio
    async def test_degraded_when_above_threshold(self):
        """latency > degraded_threshold_ms 标 degraded(可达但慢)。"""
        cfg = ProbeConfig(degraded_threshold_ms=50)  # 50ms 阈值

        def slow_handler(request: httpx.Request) -> httpx.Response:
            time.sleep(0.1)  # 100ms 故意超过 50ms 阈值
            return httpx.Response(200, content=b"")

        transport = httpx.MockTransport(slow_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://slow.example.com", config=cfg, client=client
            )
        assert result.health == "degraded"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_connect_error_returns_failed(self):
        cfg = ProbeConfig.from_raw(max_retries=0)
        transport = _make_transport([httpx.ConnectError("connection refused")])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://unreachable.example.com", config=cfg, client=client
            )
        assert result.status == "error"
        assert result.health == "failed"
        assert result.success is False
        assert result.error_category == "connect"
        assert "refused" in result.message.lower() or "connect" in result.message.lower()

    @pytest.mark.asyncio
    async def test_timeout_classified_as_timeout_category(self):
        # max_retries=0 避免「单次异常被消费 → 第二次抛 StopIteration 被当成 other」
        cfg = ProbeConfig.from_raw(max_retries=0)
        transport = _make_transport([httpx.ReadTimeout("read timed out")])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://slow.example.com", config=cfg, client=client
            )
        assert result.error_category == "timeout"
        assert result.health == "failed"

    @pytest.mark.asyncio
    async def test_timeout_retries_then_fails(self):
        """max_retries=2 → 3 次都 timeout → 最终失败并记录 retry_count=2。"""
        cfg = ProbeConfig.from_raw(timeout_secs=1, max_retries=2)
        transport = _make_transport([
            httpx.ReadTimeout("first"),
            httpx.ReadTimeout("second"),
            httpx.ReadTimeout("third"),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://example.com", config=cfg, client=client
            )
        assert result.status == "error"
        assert result.error_category == "timeout"
        assert result.retry_count == 2  # 第 3 次失败后停止

    @pytest.mark.asyncio
    async def test_timeout_then_success_recovers(self):
        """第一次 timeout,第二次成功 → 应返回成功(只有最后一次决定结果)。"""
        cfg = ProbeConfig.from_raw(timeout_secs=1, max_retries=1)
        transport = _make_transport([
            httpx.ReadTimeout("first attempt"),
            httpx.Response(200, content=b""),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://example.com", config=cfg, client=client
            )
        assert result.status == "ok"
        assert result.http_status == 200
        assert result.retry_count == 1

    @pytest.mark.asyncio
    async def test_connect_error_does_not_retry(self):
        """连接错误(端口拒绝)立即返回,不浪费时间重试。"""
        cfg = ProbeConfig.from_raw(timeout_secs=1, max_retries=2)
        transport = _make_transport([
            httpx.ConnectError("connection refused"),
            # 若重试会被消费,但不应该被消费
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://dead.example.com", config=cfg, client=client
            )
        assert result.error_category == "connect"
        assert result.retry_count == 0  # 没重试

    @pytest.mark.asyncio
    async def test_dns_error_classified(self):
        """DNS 解析失败(httpx 在 ConnectError 里抛 'Name or service not known')。"""
        cfg = ProbeConfig.from_raw(max_retries=0)
        transport = _make_transport([
            httpx.ConnectError("[Errno -2] Name or service not known")
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://no-such-host.invalid", config=cfg, client=client
            )
        # ConnectError 优先被分类为 connect,然后 message 里含 dns 关键词
        # 当前实现先归类为 connect — 这是预期的
        assert result.error_category in ("connect", "dns")

    @pytest.mark.asyncio
    async def test_tls_error_classified(self):
        cfg = ProbeConfig.from_raw(max_retries=0)
        transport = _make_transport([
            httpx.ConnectError("SSL: CERTIFICATE_VERIFY_FAILED")
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await probe_reachability(
                "https://bad-tls.example.com", config=cfg, client=client
            )
        # 同上,connect 优先
        assert result.error_category in ("connect", "tls")

    @pytest.mark.asyncio
    async def test_empty_url_returns_error(self):
        result = await probe_reachability("")
        assert result.status == "error"
        assert result.health == "failed"
        assert "URL" in result.message or "为空" in result.message

    @pytest.mark.asyncio
    async def test_user_agent_header_sent(self):
        seen_ua: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_ua.update({k.lower(): v for k, v in request.headers.items()})
            return httpx.Response(200, content=b"")

        transport = httpx.MockTransport(handler)
        cfg = ProbeConfig(user_agent="InnovOS-Admin/1.0")
        async with httpx.AsyncClient(transport=transport) as client:
            await probe_reachability(
                "https://example.com", config=cfg, client=client
            )
        assert seen_ua.get("user-agent") == "InnovOS-Admin/1.0"
        assert seen_ua.get("accept") == "*/*"

    @pytest.mark.asyncio
    async def test_accept_header_sent(self):
        """带 accept: */* 让网关返回任意响应(避免 406)。"""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen.update({k.lower(): v for k, v in request.headers.items()})
            return httpx.Response(200, content=b"")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await probe_reachability("https://example.com", client=client)
        assert seen.get("accept") == "*/*"
        assert seen.get("accept-encoding") == "identity"


# ═══════════════════════════════════════════════════════════════════════════
#  result_to_dict
# ═══════════════════════════════════════════════════════════════════════════


class TestResultToDict:
    def test_serialization_shape(self):
        from app.algorithm.reachability_probe import ProbeResult

        r = ProbeResult(
            status="ok",
            health="operational",
            success=True,
            latency_ms=123,
            http_status=200,
            message="Reachable",
            error_category=None,
            retry_count=0,
            checked_url="https://example.com",
        )
        d = result_to_dict(r)
        assert d["status"] == "ok"
        assert d["health"] == "operational"
        assert d["success"] is True
        assert d["latency_ms"] == 123
        assert d["status_code"] == 200  # 注意:字段名 status_code (兼容前端)
        assert d["checked_url"] == "https://example.com"

    def test_error_serialization(self):
        from app.algorithm.reachability_probe import ProbeResult

        r = ProbeResult(
            status="error",
            health="failed",
            success=False,
            latency_ms=5000,
            http_status=None,
            message="timed out",
            error_category="timeout",
            retry_count=1,
            checked_url="https://slow.example.com",
        )
        d = result_to_dict(r)
        assert d["status"] == "error"
        assert d["error_category"] == "timeout"
        assert d["retry_count"] == 1
