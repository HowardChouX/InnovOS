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

    降级策略（按优先级）：
    1. Redis 可用 → 分布式限流（多 worker 共享状态）
    2. Redis 不可用 → 本地内存限流（单进程有效，保底保护）
    3. 永不退化为"完全放行"——限流是安全底线

    Usage:
        limiter = RedisRateLimiter(max_requests=60, window_seconds=60)
        allowed, remaining, reset = limiter.check("192.168.1.1")
    """

    __test__ = False

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
        self._use_redis = False

        if redis_client is not None:
            self._client = redis_client
            self._use_redis = True
        elif self._redis_url:
            try:
                import redis
                self._client = redis.from_url(self._redis_url, decode_responses=True)
                self._client.ping()
                self._use_redis = True
                logger.info("已连接 Redis: %s", self._redis_url[:30])
            except Exception as e:
                logger.warning("Redis 连接失败 (%s)，降级为本地内存限流", e)
                self._init_local()
        else:
            logger.info("未配置 REDIS_URL，使用本地内存限流")
            self._init_local()

        if self._use_redis:
            self._script = self._client.register_script(_REDIS_SCRIPT)

    def _init_local(self):
        """本地内存限流：不依赖任何外部组件。"""
        self._use_redis = False
        self._local_requests: dict[str, list[float]] = {}
        self._script = lambda **kw: [1, 0, 1]  # unused for local mode

    def _key(self, client_key: str) -> str:
        return f"ratelimit:{self.name}:{client_key}"

    def check(self, key: str) -> tuple[bool, int, int]:
        """检查 key 是否允许请求。"""
        try:
            if self._use_redis:
                return self._check_redis(key)
            else:
                return self._check_local(key)
        except Exception as e:
            logger.error("Redis 限流检查失败 (%s)，降级为本地限流", e)
            self._init_local()
            return self._check_local(key)

    def _check_redis(self, key: str) -> tuple[bool, int, int]:
        now = int(time.time())
        result = self._script(
            keys=[self._key(key)],
            args=[now, self.window_seconds, self.max_requests],
        )
        return bool(result[0]), int(result[1]), int(result[2])

    def _check_local(self, key: str) -> tuple[bool, int, int]:
        """本地内存滑动窗口限流（降级方案）。"""
        now = time.time()
        full_key = self._key(key)
        window = self.window_seconds

        # 清理过期记录
        if full_key not in self._local_requests:
            self._local_requests[full_key] = []
        self._local_requests[full_key] = [
            t for t in self._local_requests[full_key] if now - t < window
        ]

        count = len(self._local_requests[full_key])
        remaining = max(0, self.max_requests - count - 1)

        if count < self.max_requests:
            self._local_requests[full_key].append(now)
            reset = window
            return True, remaining, reset
        else:
            oldest = self._local_requests[full_key][0]
            reset_in = int(window - (now - oldest))
            return False, 0, max(1, reset_in)

    def get_remaining(self, key: str) -> int:
        try:
            if self._use_redis:
                now = int(time.time())
                cutoff = now - self.window_seconds
                client = self._client
                redis_key = self._key(key)
                client.zremrangebyscore(redis_key, 0, cutoff)
                count = client.zcard(redis_key)
                return max(0, self.max_requests - count)
            else:
                now = time.time()
                full_key = self._key(key)
                if full_key not in self._local_requests:
                    return self.max_requests
                valid = [t for t in self._local_requests[full_key] if now - t < self.window_seconds]
                return max(0, self.max_requests - len(valid))
        except Exception as e:
            logger.error("Redis 查询剩余失败: %s", e)
            return 0

    def get_reset(self, key: str) -> int:
        try:
            if self._use_redis:
                now = int(time.time())
                client = self._client
                redis_key = self._key(key)
                oldest = client.zrange(redis_key, 0, 0, withscores=True)
                if oldest:
                    reset_in = self.window_seconds - (now - int(oldest[0][1]))
                    return max(1, reset_in)
                return 0
            else:
                now = time.time()
                full_key = self._key(key)
                if full_key not in self._local_requests or not self._local_requests[full_key]:
                    return 0
                valid = [t for t in self._local_requests[full_key] if now - t < self.window_seconds]
                if not valid:
                    return 0
                return max(1, int(self.window_seconds - (now - valid[0])))
        except Exception as e:
            logger.error("Redis 查询重置时间失败: %s", e)
            return 0

    def cleanup(self):
        pass

    @property
    def client(self):
        return self._client if self._use_redis else None


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

# ── 邮件 OTP 限流器 ────────────────────────────────────
# 每个邮箱地址每 60s 最多请求 1 次 OTP（resend）
email_otp_request_limiter = RedisRateLimiter(max_requests=1, window_seconds=60, name="email_otp_req")
# 每个邮箱地址每 60s 最多验证 10 次
email_otp_verify_limiter = RedisRateLimiter(max_requests=10, window_seconds=60, name="email_otp_verify")
# 每个 IP 每 60s 最多 30 次 OTP 相关操作（兜底防滥用）
email_otp_ip_limiter = RedisRateLimiter(max_requests=30, window_seconds=60, name="email_otp_ip")
