"""
API Key管理器 — 从环境变量读取密钥，不再使用数据库存储

功能：
1. Key池轮询（支持按 Provider 过滤）
2. 并发控制（信号量）
3. 限流检测
4. 自动切换失败Key
"""

import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)


class APIKeyManager:
    def __init__(self):
        # 并发控制：最多同时5个请求
        self._semaphore = asyncio.Semaphore(5)
        # 当前Key索引（轮询，按 provider 分组）
        self._current_index: dict[str, int] = {}
        # Key缓存（按 provider 分组）
        self._keys_cache: dict[str, list] = {}
        self._cache_updated_at: float = 0
        # 缓存过期时间（秒）
        self._cache_ttl = 30

    async def acquire(self):
        """获取并发许可"""
        await self._semaphore.acquire()

    def release(self):
        """释放并发许可"""
        self._semaphore.release()

    def _load_keys_from_env(self) -> dict[str, list]:
        """扫描环境变量 AI_{PROVIDER_ID}_API_KEY 模式并构建缓存。"""
        grouped: dict[str, list] = {}
        for env_key, val in os.environ.items():
            upper = env_key.upper()
            if not upper.startswith("AI_") or not upper.endswith("_API_KEY"):
                continue
            # 提取 provider_id: AI_{PROVIDER}_API_KEY 或 AI_{PROVIDER}_API_KEY_{N}
            middle = upper[3:-8]  # 去掉 "AI_" 前缀和 "_API_KEY" 后缀
            parts = middle.rsplit("_", 1)
            if parts[-1].isdigit():
                provider_id = "_".join(parts[:-1])
                key_index = int(parts[-1])
            else:
                provider_id = middle
                key_index = 0
            if not provider_id:
                continue
            if provider_id not in grouped:
                grouped[provider_id] = []
            # 可选从环境变量读取 host 和 model
            host_key = f"AI_{provider_id}_API_HOST"
            api_host = os.getenv(host_key, "")
            model_key = f"AI_{provider_id}_API_MODEL"
            api_model = os.getenv(model_key, "")
            grouped[provider_id].append(
                {
                    "api_key": val,
                    "api_host": api_host,
                    "api_model": api_model,
                    "key_index": key_index,
                    "id": f"env_{provider_id}_{key_index}",
                    "max_rpm": 60,
                    "current_rpm": 0,
                    "last_reset_at": None,
                }
            )
        return grouped

    def _refresh_keys_cache(self):
        """刷新Key缓存（按 provider 分组）"""
        now = time.time()
        if now - self._cache_updated_at < self._cache_ttl:
            return
        self._keys_cache = self._load_keys_from_env()
        self._cache_updated_at = now

    def _get_next_key(self, provider_id: str = "") -> dict:
        """获取下一个可用的Key（轮询），支持按 provider 过滤"""
        self._refresh_keys_cache()

        # 获取指定 provider 的 keys，或所有 keys
        if provider_id:
            keys = self._keys_cache.get(provider_id, [])
        else:
            # 合并所有 provider 的 keys
            keys = [k for pool in self._keys_cache.values() for k in pool]

        if keys:
            idx = self._current_index.get(provider_id, 0) % len(keys)
            key = keys[idx]
            self._current_index[provider_id] = idx + 1
            return key

        raise RuntimeError("未配置任何可用的API Key，请在环境变量 AI_{ID}_API_KEY 中设置")

    def _check_rate_limit(self, key: dict) -> bool:
        """检查Key是否达到限流（简化的内存限流检查，不再查数据库）"""
        # 简易内存限流：每分钟最多 max_rpm 次
        if key.get("current_rpm", 0) >= key.get("max_rpm", 60):
            return False
        return True

    async def get_key_for_request(self, provider_id: str = "") -> dict:
        """获取适合当前请求的Key

        Args:
            provider_id: 指定供应商ID，为空则轮询所有可用Key
        """
        keys = self._keys_cache.get(provider_id, [])
        for _ in range(min(len(keys) or 1, 10)):
            key = self._get_next_key(provider_id)
            if self._check_rate_limit(key):
                return key

        await asyncio.sleep(1)
        return self._get_next_key(provider_id)


# 全局实例
key_manager = APIKeyManager()
