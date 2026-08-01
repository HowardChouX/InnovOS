"""供应商连通性探测 — 参考 cc-switch ``services/stream_check.rs``。

设计原则(**故意不发送真实大模型请求**):
- 仅对 ``base_url`` 发 GET,任何 HTTP 响应(2xx/4xx/5xx)都判定可达
- 仅 DNS / 连接被拒 / TLS / 超时等**网络级错误**判定不可达
- 不消耗 token、不被鉴权/限流干扰;代价是无法告诉你鉴权对不对
- 计时 = TTFB(Time To First Byte),``send().await`` 收到响应头即停
- 超时类失败重试 ``max_retries`` 次;连接被拒/DNS 失败等不重试
- latency > ``degraded_threshold_ms`` 标 Degraded(可达但慢)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECS: float = 8.0
MIN_TIMEOUT_SECS: float = 2.0
MAX_TIMEOUT_SECS: float = 30.0
DEFAULT_DEGRADED_THRESHOLD_MS: int = 6000
DEFAULT_MAX_RETRIES: int = 1


@dataclass(slots=True)
class ProbeConfig:
    """探测配置(单一来源,避免 magic numbers 散落各处)。"""

    timeout_secs: float = DEFAULT_TIMEOUT_SECS
    degraded_threshold_ms: int = DEFAULT_DEGRADED_THRESHOLD_MS
    max_retries: int = DEFAULT_MAX_RETRIES
    user_agent: str | None = None

    @classmethod
    def from_raw(
        cls,
        timeout_secs: float | None = None,
        degraded_threshold_ms: int | None = None,
        max_retries: int | None = None,
        user_agent: str | None = None,
    ) -> ProbeConfig:
        return cls(
            timeout_secs=_clamp_timeout(timeout_secs),
            degraded_threshold_ms=degraded_threshold_ms or DEFAULT_DEGRADED_THRESHOLD_MS,
            max_retries=max(0, max_retries if max_retries is not None else DEFAULT_MAX_RETRIES),
            user_agent=user_agent or None,
        )


def _clamp_timeout(timeout_secs: float | None) -> float:
    """钳制 timeout 到合理区间,避免过快(误杀)或过慢(阻塞 UI)。"""
    if timeout_secs is None:
        return DEFAULT_TIMEOUT_SECS
    return float(max(MIN_TIMEOUT_SECS, min(MAX_TIMEOUT_SECS, timeout_secs)))


@dataclass(slots=True)
class ProbeResult:
    """连通性探测结果。

    字段对齐 cc-switch ``StreamCheckResult``,但保留 InnovOS 既有 ``status``
    (ok/error) 字符串以兼容前端 alert 文案。
    """

    status: str  # "ok" | "error"
    health: str  # "operational" | "degraded" | "failed"
    success: bool
    latency_ms: int | None
    http_status: int | None
    message: str
    error_category: str | None  # "timeout" | "connect" | "dns" | "tls" | "other"
    retry_count: int
    checked_url: str


def _classify_error(exc: httpx.HTTPError) -> str:
    """把 httpx 异常分类,便于前端展示和告警分流。"""
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connect"
    if isinstance(exc, httpx.UnsupportedProtocol):
        return "protocol"
    # RemoteProtocolError / NetworkError / 其他
    msg = str(exc).lower()
    if "dns" in msg or "name resolution" in msg or "getaddrinfo" in msg:
        return "dns"
    if "ssl" in msg or "tls" in msg or "certificate" in msg:
        return "tls"
    return "other"


def _is_retryable(category: str) -> bool:
    """仅 timeout / abort 类网络抖动值得重试;连接被拒 / DNS 失败 / TLS 错立即返回。"""
    return category in ("timeout",)


def _should_retry_message(message: str) -> bool:
    """兼容旧 message 字符串判断(cc-switch 风格)。"""
    lower = message.lower()
    return "timeout" in lower or "abort" in lower or "timed out" in lower


async def probe_reachability(
    url: str,
    *,
    config: ProbeConfig | None = None,
    client: httpx.AsyncClient | None = None,
) -> ProbeResult:
    """对单个 URL 做连通性探测(GET base_url,TTFB 计时,自动重试)。

    参数:
        url: 要探测的 base URL(任何 HTTP 响应即视为可达)
        config: 探测配置;None 用默认值
        client: 可选外部 httpx 客户端(测试用)
    """
    cfg = config or ProbeConfig()
    target = url.strip()
    if not target:
        return ProbeResult(
            status="error",
            health="failed",
            success=False,
            latency_ms=None,
            http_status=None,
            message="URL 为空",
            error_category="other",
            retry_count=0,
            checked_url=url,
        )

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=cfg.timeout_secs)

    headers: dict[str, str] = {"accept": "*/*", "accept-encoding": "identity"}
    if cfg.user_agent:
        headers["user-agent"] = cfg.user_agent

    last_result: ProbeResult | None = None
    try:
        for attempt in range(cfg.max_retries + 1):
            started = time.perf_counter()
            try:
                resp = await client.get(target, headers=headers)  # type: ignore[union-attr]
            except httpx.HTTPError as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                category = _classify_error(exc)
                message = str(exc)[:200]
                last_result = ProbeResult(
                    status="error",
                    health="failed",
                    success=False,
                    latency_ms=elapsed_ms,
                    http_status=None,
                    message=message,
                    error_category=category,
                    retry_count=attempt,
                    checked_url=target,
                )
                # 仅 timeout 重试;其他错误立即返回
                if _is_retryable(category) and attempt < cfg.max_retries:
                    continue
                return last_result
            except Exception as exc:  # noqa: BLE001
                # 非 HTTPError(如 URL 解析错)直接失败
                return ProbeResult(
                    status="error",
                    health="failed",
                    success=False,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    http_status=None,
                    message=str(exc)[:200],
                    error_category="other",
                    retry_count=attempt,
                    checked_url=target,
                )
            else:
                # 收到响应头(任何 HTTP 状态都算可达)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                http_status = resp.status_code
                health = (
                    "operational"
                    if elapsed_ms <= cfg.degraded_threshold_ms
                    else "degraded"
                )
                return ProbeResult(
                    status="ok",
                    health=health,
                    success=True,
                    latency_ms=elapsed_ms,
                    http_status=http_status,
                    message="Reachable",
                    error_category=None,
                    retry_count=attempt,
                    checked_url=target,
                )
    finally:
        if owns_client:
            await client.aclose()  # type: ignore[union-attr]

    # 循环正常结束(应不会到达这里)— 兜底返回最后一次结果
    assert last_result is not None
    return last_result


async def probe_with_retry_message_fallback(
    url: str,
    *,
    config: ProbeConfig | None = None,
) -> ProbeResult:
    """``probe_reachability`` 的便捷包装(无外部 client 时使用)。

    保留这个 alias 是为了兼容旧测试用 message 判断重试的逻辑路径。
    """
    return await probe_reachability(url, config=config)


def result_to_dict(result: ProbeResult) -> dict[str, Any]:
    """把 ProbeResult 序列化成前端友好的 dict。

    兼容前端既有 ``status`` / ``status_code`` / ``latency_ms`` 字段。
    """
    out: dict[str, Any] = {
        "status": result.status,
        "health": result.health,
        "success": result.success,
        "latency_ms": result.latency_ms,
        "status_code": result.http_status,
        "message": result.message,
        "error_category": result.error_category,
        "retry_count": result.retry_count,
        "checked_url": result.checked_url,
    }
    return out
