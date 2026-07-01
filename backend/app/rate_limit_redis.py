"""
Redis 滑动窗口限流器 — 替代内存版 RateLimiter。

使用 Redis Sorted Set + Lua 脚本实现原子滑动窗口。
适合多 worker / 多服务器部署，共享同一限流状态。
"""

from __future__ import annotations

import logging
import os
import time

from starlette.requests import Request

_REDIS_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local count = redis.call('ZCARD', key)

if count < max_requests then
    local member = now .. ":" .. count
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window + 1)
    return {1, max_requests - count - 1, window}
end

local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
if oldest and #oldest >= 2 then
    local reset_in = window - (now - tonumber(oldest[2]))
    if reset_in < 1 then reset_in = 1 end
    return {0, 0, reset_in}
end
return {0, 0, window}
"""

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """Redis 滑动窗口限流器。

    Usage:
        limiter = RedisRateLimiter(max_requests=60, window_seconds=60)
        allowed, remaining, reset = limiter.check("192.168.1.1")
    """

    __test__ = False  # Prevent pytest from collecting this as a test

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        redis_client=None,
        name: str = "default",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._redis_url = os.getenv("REDIS_URL", "")

        if redis_client is not None:
            self._client = redis_client
        elif self._redis_url:
            import redis

            self._client = redis.from_url(self._redis_url, decode_responses=True)
            logger.info("已连接 Redis: %s", self._redis_url[:30])
        else:
            try:
                import fakeredis

                self._client = fakeredis.FakeStrictRedis()
                logger.warning("未配置 REDIS_URL，使用 fakeredis 内存模拟（仅开发/测试用）")
            except ImportError:
                from unittest.mock import MagicMock

                self._client = MagicMock()
                logger.warning("未配置 REDIS_URL 且 fakeredis 未安装，限流功能降级为放行")
                self._script = lambda **kw: [1, 0, 1]  # degraded: pass-through
                return

        # 注册 Lua 脚本
        self._script = self._client.register_script(_REDIS_SCRIPT)

    def _key(self, client_key: str) -> str:
        """生成 Redis key。"""
        return f"ratelimit:{self.name}:{client_key}"

    def check(self, key: str) -> tuple[bool, int, int]:
        """检查 key 是否允许请求。

        Returns:
            (allowed, remaining, reset_seconds)
        """
        try:
            now = int(time.time())
            result = self._script(
                keys=[self._key(key)],
                args=[now, self.window_seconds, self.max_requests],
            )
            allowed = bool(result[0])
            remaining = int(result[1])
            reset_seconds = int(result[2])
            return allowed, remaining, reset_seconds
        except Exception as e:
            logger.error("Redis 限流检查失败: %s", e)
            raise ConnectionError(f"Redis 限流检查失败: {e}") from e

    def get_remaining(self, key: str) -> int:
        """获取剩余可用请求数。"""
        try:
            now = int(time.time())
            cutoff = now - self.window_seconds
            client = self._client
            redis_key = self._key(key)
            client.zremrangebyscore(redis_key, 0, cutoff)
            count = client.zcard(redis_key)
            return max(0, self.max_requests - count)
        except Exception as e:
            logger.error("Redis 查询剩余失败: %s", e)
            return 0

    def get_reset(self, key: str) -> int:
        """获取窗口重置剩余秒数。"""
        try:
            now = int(time.time())
            client = self._client
            redis_key = self._key(key)
            oldest = client.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                reset_in = self.window_seconds - (now - int(oldest[0][1]))
                return max(1, reset_in)
            return 0
        except Exception as e:
            logger.error("Redis 查询重置时间失败: %s", e)
            return 0

    def cleanup(self):
        """清理所有过期 key（调用 Redis 端过期机制自动处理）。"""
        pass

    @property
    def client(self):
        """暴露 Redis 客户端（用于测试/调试）。"""
        return self._client


def get_client_ip(request: Request) -> str:
    """从请求中提取真实客户端 IP。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


# ── 全局限流器实例（与旧接口兼容） ──────────────────────
auth_limiter = RedisRateLimiter(max_requests=10, window_seconds=60, name="auth")
register_limiter = RedisRateLimiter(max_requests=3, window_seconds=300, name="register")
api_limiter = RedisRateLimiter(max_requests=120, window_seconds=60, name="api")
