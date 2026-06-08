"""
向量嵌入服务 — 支持远程 API 和本地模型

借鉴 CherryStudio embed.ts：embedMany() 模式
"""
from __future__ import annotations
import json
import math
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
            try:
                return await self._remote_embed(texts)
            except Exception as e:
                logger.warning(f"远程嵌入失败 {e}")
        return [self._local_embed(t) for t in texts]

    async def _remote_embed(self, texts: list[str]) -> list[list[float]]:
        """远程 Embedding API — OpenAI 兼容格式 /v1/embeddings。"""
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.api_host}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"input": texts, "model": self.model},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Embedding API error: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            # 按 input 顺序返回
            indexed = {item["index"]: item["embedding"] for item in data.get("data", [])}
            embeddings = [indexed[i] for i in range(len(texts))]
            if embeddings and len(embeddings[0]) > 0:
                self._dim = len(embeddings[0])
            return embeddings

    def _local_embed(self, text: str, dim: int = 384) -> list[float]:
        """纯 Python hash 嵌入。"""
        import hashlib
        text = text.lower().strip()
        vec = {}
        for i in range(0, len(text), 2):
            gram = text[i:i + 2]
            h = hashlib.md5(gram.encode()).digest()
            for j in range(8):
                idx = (i + j) % dim
                val = (h[j] - 128) / 128.0
                vec[idx] = vec.get(idx, 0) + val
        result = [vec.get(i, 0.0) for i in range(dim)]
        norm = math.sqrt(sum(x * x for x in result))
        if norm > 0:
            result = [x / norm for x in result]
        return result

    @property
    def dimension(self) -> int:
        return self._dim
