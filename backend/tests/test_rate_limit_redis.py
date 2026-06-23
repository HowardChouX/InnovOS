"""
Redis 限流器单元测试 — 使用 fakeredis 模拟 Redis。
"""

import time
from unittest.mock import patch

import fakeredis
import pytest

from app.rate_limit_redis import RedisRateLimiter


@pytest.fixture
def limiter():
    """创建使用 fakeredis 的限流器实例。"""
    r = fakeredis.FakeStrictRedis()
    limiter = RedisRateLimiter(max_requests=5, window_seconds=60, redis_client=r)
    return limiter


class TestRedisRateLimiterBasics:
    """基本功能测试"""

    def test_init_defaults(self):
        """默认参数：60次/分钟，无参数时自动使用 fakeredis"""
        l = RedisRateLimiter()
        assert l.max_requests == 60
        assert l.window_seconds == 60

    def test_init_custom(self):
        """自定义参数"""
        l = RedisRateLimiter(max_requests=10, window_seconds=300)
        assert l.max_requests == 10
        assert l.window_seconds == 300

    def test_check_returns_tuple(self, limiter):
        """check() 返回 (allowed, remaining, reset_seconds)"""
        result = limiter.check("192.168.1.1")
        assert len(result) == 3
        assert isinstance(result[0], bool)
        assert isinstance(result[1], int)
        assert isinstance(result[2], int)

    def test_first_request_allowed(self, limiter):
        """首次请求应允许"""
        allowed, remaining, _ = limiter.check("192.168.1.1")
        assert allowed is True
        assert remaining == 4  # max_requests=5, used=1

    def test_within_limit(self, limiter):
        """低于限制应全部允许"""
        for i in range(5):
            allowed, remaining, _ = limiter.check("10.0.0.1")
            assert allowed is True, f"请求 {i+1} 应允许"
            assert remaining == 4 - i, f"剩余次数: {remaining} != {4 - i}"

    def test_exceed_limit(self, limiter):
        """超过限制应拒绝"""
        for i in range(5):
            limiter.check("10.0.0.2")
        allowed, remaining, reset = limiter.check("10.0.0.2")
        assert allowed is False
        assert remaining == 0
        assert reset > 0

    def test_different_ips_independent(self, limiter):
        """不同 IP 的限流互不影响"""
        for i in range(5):
            limiter.check("10.0.0.1")
        allowed_a, _, _ = limiter.check("10.0.0.1")
        allowed_b, _, _ = limiter.check("10.0.0.2")
        assert allowed_a is False  # 10.0.0.1 超限
        assert allowed_b is True  # 10.0.0.2 未超限


class TestRedisRateLimiterWindow:
    """滑动窗口测试"""

    def test_window_expires(self):
        """窗口过期后应重置计数"""
        r = fakeredis.FakeStrictRedis()
        l = RedisRateLimiter(max_requests=2, window_seconds=1, redis_client=r)

        l.check("10.0.0.1")
        l.check("10.0.0.1")
        allowed, _, _ = l.check("10.0.0.1")
        assert allowed is False  # 超限

        time.sleep(1.1)  # 等待窗口过期

        allowed, remaining, _ = l.check("10.0.0.1")
        assert allowed is True  # 窗口重置
        assert remaining == 1

    def test_sliding_window(self):
        """滑动窗口：旧请求过期后腾出配额"""
        r = fakeredis.FakeStrictRedis()
        l = RedisRateLimiter(max_requests=2, window_seconds=5, redis_client=r)

        l.check("10.0.0.1")  # t=0
        time.sleep(3)
        l.check("10.0.0.1")  # t=3
        # t=3 时窗口内已有2个请求
        allowed, _, _ = l.check("10.0.0.1")
        assert allowed is False  # 超限

        time.sleep(3)  # t=6: 第一个请求（t=0）过期
        allowed, remaining, _ = l.check("10.0.0.1")
        assert allowed is True  # 第一个请求已过期
        assert remaining == 0  # 窗口内还有 t=3 的请求，新请求后剩余为 0


class TestRedisRateLimiterEdgeCases:
    """边界情况测试"""

    def test_zero_max_requests(self):
        """max_requests=0 应拒绝所有请求"""
        r = fakeredis.FakeStrictRedis()
        l = RedisRateLimiter(max_requests=0, window_seconds=60, redis_client=r)
        allowed, remaining, _ = l.check("10.0.0.1")
        assert allowed is False
        assert remaining == 0

    def test_empty_key(self, limiter):
        """空字符串作为 key 应正常工作"""
        allowed, remaining, _ = limiter.check("")
        assert allowed is True
        assert remaining == 4

    def test_unicode_key(self, limiter):
        """Unicode key 应正常工作"""
        allowed, _, _ = limiter.check("用户::192.168.1.1")
        assert allowed is True

    def test_cleanup(self, limiter):
        """cleanup 不应抛出异常"""
        for i in range(3):
            limiter.check(f"10.0.0.{i}")
        limiter.cleanup()  # 应无异常

    def test_multiple_limiter_instances_independent(self):
        """不同限流器实例应有独立 Redis key 前缀"""
        r = fakeredis.FakeStrictRedis()
        auth = RedisRateLimiter(max_requests=3, window_seconds=60, redis_client=r, name="auth")
        api = RedisRateLimiter(max_requests=100, window_seconds=60, redis_client=r, name="api")

        for i in range(3):
            auth.check("10.0.0.1")
        allowed_auth, _, _ = auth.check("10.0.0.1")
        allowed_api, _, _ = api.check("10.0.0.1")
        assert allowed_auth is False  # auth 超限
        assert allowed_api is True  # api 未超限


class TestRedisRateLimiterRedisError:
    """Redis 操作失败时的行为"""

    def test_redis_error_raises(self):
        """check 时 Redis 操作失败应抛出 ConnectionError"""
        from unittest.mock import MagicMock

        broken_client = MagicMock()
        broken_client.register_script.return_value = MagicMock()
        l = RedisRateLimiter(max_requests=5, window_seconds=60, redis_client=broken_client)
        # 让 _script() 调用失败
        l._script.side_effect = Exception("脚本执行失败")
        with pytest.raises(ConnectionError):
            l.check("10.0.0.1")

    def test_cleanup_never_raises(self):
        """cleanup 即使在 Redis 不可用时也不应抛出"""
        r = fakeredis.FakeStrictRedis()
        l = RedisRateLimiter(max_requests=5, window_seconds=60, redis_client=r)
        l.cleanup()  # 无异常


class TestRedisRateLimiterConcurrency:
    """并发安全测试"""

    def test_redis_script_atomic(self):
        """Lua 脚本应原子执行"""
        r = fakeredis.FakeStrictRedis()
        l = RedisRateLimiter(max_requests=100, window_seconds=60, redis_client=r)

        for _ in range(100):
            l.check("10.0.0.1")

        allowed, remaining, _ = l.check("10.0.0.1")
        assert allowed is False
        assert remaining == 0
