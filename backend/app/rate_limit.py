"""
Simple in-memory sliding window rate limiter.

每 IP 独立窗口，无需外部依赖（Redis）。适用于中小规模部署。
"""

import time
from collections import defaultdict


class RateLimiter:
    """
    In-memory rate limiter — works per-process only.
    For multi-worker deployments, replace with Redis-backed implementation.

    滑动窗口限流器。

    Usage:
        limiter = RateLimiter(max_requests=60, window_seconds=60)
        allowed, remaining, reset = limiter.check("192.168.1.1")
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> tuple[bool, int, int]:
        """检查 key 是否允许请求。

        Returns:
            (allowed, remaining, reset_seconds)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # 清除过期记录
        bucket = self._buckets[key]
        while bucket and bucket[0] < window_start:
            bucket.pop(0)

        if len(bucket) >= self.max_requests:
            # 计算窗口重置时间
            reset_at = bucket[0] + self.window_seconds
            reset_seconds = max(1, int(reset_at - now))
            return False, 0, reset_seconds

        bucket.append(now)
        remaining = self.max_requests - len(bucket)
        return True, remaining, int(self.window_seconds)

    def get_remaining(self, key: str) -> int:
        """获取剩余可用请求数。"""
        now = time.time()
        window_start = now - self.window_seconds
        bucket = self._buckets.get(key, [])
        # 清理过期
        while bucket and bucket[0] < window_start:
            bucket.pop(0)
        return self.max_requests - len(bucket)

    def get_reset(self, key: str) -> int:
        """获取窗口重置剩余秒数。"""
        now = time.time()
        window_start = now - self.window_seconds
        bucket = self._buckets.get(key, [])
        while bucket and bucket[0] < window_start:
            bucket.pop(0)
        if bucket:
            return max(1, int(bucket[0] + self.window_seconds - now))
        return 0

    def cleanup(self):
        """清理所有过期 bucket（定时任务调用）。"""
        now = time.time()
        window_start = now - self.window_seconds
        for key in list(self._buckets.keys()):
            bucket = self._buckets[key]
            while bucket and bucket[0] < window_start:
                bucket.pop(0)
            if not bucket:
                del self._buckets[key]

    async def periodic_cleanup(self, interval_seconds: int = 300):
        """Periodically clean expired entries from the rate limiter buckets."""
        import asyncio

        while True:
            await asyncio.sleep(interval_seconds)
            now = time.time()
            to_remove = []
            for ip, timestamps in list(self._buckets.items()):
                cutoff = now - self.window_seconds
                valid = [ts for ts in timestamps if ts > cutoff]
                if valid:
                    self._buckets[ip] = valid
                else:
                    to_remove.append(ip)
            for ip in to_remove:
                self._buckets.pop(ip, None)


# 全局实例
auth_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 登录 10次/分钟
register_limiter = RateLimiter(max_requests=3, window_seconds=300)  # 注册 3次/5分钟
api_limiter = RateLimiter(max_requests=120, window_seconds=60)  # 通用 API 120次/分钟


def get_client_ip(request) -> str:
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
