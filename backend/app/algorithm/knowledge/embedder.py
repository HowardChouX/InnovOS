"""
向量嵌入服务 — 调用远程 API，失败即报错（无降级）

与 CherryStudio 行为一致：模型失败 → 异常冒泡 → job 重试 → 标记 failed
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class Embedder:
    """向量嵌入服务。"""

    def __init__(self, api_key: str = "", api_host: str = "", model: str = ""):
        self.api_key = api_key
        self.api_host = api_host.rstrip("/")
        self.model = model or "BAAI/bge-large-zh-v1.5"
        self._dim = 1024

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.api_key and self.api_host:
            return await self._remote_embed(texts)
        raise RuntimeError("未配置嵌入模型 API（需要 api_key 和 api_host）")

    def _embedding_url(self) -> str:
        """规范化 Embedding API URL — 处理是否含 /v1 路径前缀。

        OpenAI 兼容格式要求 POST {host}/v1/embeddings。
        如果 api_host 已经包含了 /v1 或显式 /embeddings，直接使用；否则补全 /v1。
        """
        host = self.api_host.rstrip("/")
        if host.endswith("/embeddings"):
            return host
        if any(host.endswith(s) for s in ("/v1", "/v2", "/api")):
            return f"{host}/embeddings"
        return f"{host}/v1/embeddings"

    async def _remote_embed(self, texts: list[str]) -> list[list[float]]:
        """远程 Embedding API — OpenAI 兼容格式 POST /v1/embeddings。

        分批发送（每批最多 8 条），因为 Qwen 等模型 API 超过 8 条时 index 会重复。
        """
        import httpx

        # 每批最多 8 条（Qwen/Qwen3-VL-Embedding-8B 限制）
        BATCH_SIZE = 8
        url = self._embedding_url()

        async def _embed_batch(batch: list[str]) -> list[list[float]]:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"input": batch, "model": self.model},
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"嵌入模型 API 返回 {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                items = data.get("data", [])
                if not items:
                    raise RuntimeError("嵌入模型 API 返回空数据")
                # 同一批内按 index 排序（Qwen 响应固定 0..N-1）
                items.sort(key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in items]

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            batch_embeddings = await _embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        if all_embeddings and len(all_embeddings[0]) > 0:
            self._dim = len(all_embeddings[0])
        return all_embeddings

    @property
    def dimension(self) -> int:
        return self._dim
