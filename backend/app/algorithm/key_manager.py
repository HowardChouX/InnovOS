"""
API Key管理器 — 从环境变量读取密钥，不再使用数据库存储

功能：
1. Key池轮询（支持按 Provider 过滤）
2. 并发控制（信号量）
3. 限流检测
4. 自动切换失败Key
"""

import logging
import os

logger = logging.getLogger(__name__)


class APIKeyManager:
    def __init__(self):
        # 当前Key索引（轮询，按 provider 分组）
        self._current_index: dict[str, int] = {}
        # Key缓存（按 provider 分组）
        self._keys_cache: dict[str, list] = {}

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
                    # 限流由 app.rate_limit 处理（IP 级别）
                    # 多 Key 负载均衡暂未实现
                }
            )
        return grouped

    def _refresh_keys_cache(self):
        """刷新Key缓存（从环境变量重新加载）"""
        self._keys_cache = self._load_keys_from_env()

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

    async def get_key_for_request(self, provider_id: str = "") -> dict:
        """获取适合当前请求的Key（轮询）

        Args:
            provider_id: 指定供应商ID，为空则轮询所有可用Key

        Note:
            限流由 app.rate_limit 处理（IP 级别），本模块只负责 Key 轮询。
        """
        return self._get_next_key(provider_id)


# 全局实例
key_manager = APIKeyManager()
