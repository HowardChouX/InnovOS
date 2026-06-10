"""
重排服务 — OpenAI 兼容的重排序 API

借鉴 CherryStudio:
- RerankingModelV3 (ai-sdk-provider)
- RerankAdapter (services/knowledge/rerank/)
- GeneralReranker (knowledge/reranker/)

支持供应商：
- SiliconFlow / OpenAI 兼容格式: POST /rerank
- DashScope (百炼): 独立 URL 格式
- TEI (Text Embedding Inference): POST /rerank
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Reranker:
    """重排服务 — 对向量检索结果进行二次排序。"""

    def __init__(self, api_key: str = "", api_host: str = "", model: str = "", endpoint_type: str = ""):
        self.api_key = api_key
        self.api_host = api_host.rstrip("/")
        self.model = model or "BAAI/bge-reranker-v2-m3"
        self.endpoint_type = endpoint_type

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 10,
    ) -> list[dict]:
        """对文档列表进行重排。

        Args:
            query: 查询文本
            documents: 待重排的文档列表
            top_n: 返回 Top-N 结果

        Returns:
            [{index: int, relevance_score: float, text: str}, ...]
            按 relevance_score 降序排列
        """
        if not query or not documents:
            return []

        if self.api_key and self.api_host:
            try:
                return await self._remote_rerank(query, documents, top_n)
            except Exception as e:
                logger.warning(f"远程重排失败: {e}")

        # 降级：返回原始顺序，score 设为 0
        logger.warning("重排降级：无有效 API 配置，返回原始顺序")
        return [
            {"index": i, "relevance_score": 0.0, "text": doc}
            for i, doc in enumerate(documents[:top_n])
        ]

    async def _remote_rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict]:
        """远程重排 API — 根据供应商类型选择不同的调用方式。"""
        provider_type = self._detect_provider()

        if provider_type == "dashscope":
            return await self._rerank_dashscope(query, documents, top_n)
        elif provider_type == "tei":
            return await self._rerank_tei(query, documents, top_n)

        # 默认：OpenAI 兼容格式 POST /rerank
        return await self._rerank_openai_compat(query, documents, top_n)

    async def _rerank_openai_compat(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict]:
        """OpenAI 兼容重排 API。

        请求格式：
          POST {base_url}/rerank
          {"model": "...", "query": "...", "documents": [...], "top_n": N}

        响应格式：
          {"results": [{"index": 0, "relevance_score": 0.95}, ...]}
        """
        import httpx

        base = self.api_host.rstrip("/")
        if base.endswith("/v1"):
            url = f"{base}/rerank"
        else:
            url = f"{base}/v1/rerank"
        body = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )

            if resp.status_code != 200:
                raise RuntimeError(f"Rerank API error: {resp.status_code} {resp.text[:300]}")

            data = resp.json()

        # 解析响应（兼容多种格式）
        results = data.get("results", data.get("data", []))
        if not results and isinstance(data, list):
            results = data

        parsed = []
        for item in results:
            idx = item.get("index", item.get("originalIndex", len(parsed)))
            score = item.get("relevance_score", item.get("score", item.get("relevanceScore", 0.0)))
            text = item.get("text", "")
            if not text and idx < len(documents):
                text = documents[idx]
            parsed.append({
                "index": idx,
                "relevance_score": score,
                "text": text,
            })

        # 按分数降序
        parsed.sort(key=lambda x: x["relevance_score"], reverse=True)
        return parsed

    async def _rerank_dashscope(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict]:
        """阿里百炼 DashScope 重排 API。"""
        import httpx

        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank"
        body = {
            "model": self.model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "top_n": top_n,
            },
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )

            if resp.status_code != 200:
                raise RuntimeError(f"DashScope Rerank error: {resp.status_code} {resp.text[:300]}")

            data = resp.json()

        results = data.get("output", {}).get("results", [])
        parsed = []
        for item in results:
            idx = item.get("index", len(parsed))
            score = item.get("relevance_score", 0.0)
            parsed.append({
                "index": idx,
                "relevance_score": score,
                "text": documents[idx] if idx < len(documents) else "",
            })

        parsed.sort(key=lambda x: x["relevance_score"], reverse=True)
        return parsed

    async def _rerank_tei(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict]:
        """TEI (Text Embedding Inference) 重排 API。

        格式：POST /rerank
        body: {"query": "...", "texts": [...], "return_text": true}
        """
        import httpx

        url = f"{self.api_host}/rerank"
        body = {
            "query": query,
            "texts": documents,
            "return_text": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )

            if resp.status_code != 200:
                raise RuntimeError(f"TEI Rerank error: {resp.status_code} {resp.text[:300]}")

            data = resp.json()

        results = data if isinstance(data, list) else data.get("results", [])
        parsed = []
        for item in results:
            idx = item.get("index", len(parsed))
            score = item.get("score", item.get("relevance_score", 0.0))
            text = item.get("text", documents[idx] if idx < len(documents) else "")
            parsed.append({
                "index": idx,
                "relevance_score": score,
                "text": text,
            })

        parsed.sort(key=lambda x: x["relevance_score"], reverse=True)
        return parsed

    def _detect_provider(self) -> str:
        """检测供应商类型。优先使用显式 endpoint_type，其次从 host 推断。"""
        if self.endpoint_type:
            if "jina-rerank" in self.endpoint_type.lower():
                return "jina"
            if "tei" in self.endpoint_type.lower():
                return "tei"
            if "dashscope" in self.endpoint_type.lower() or "bailian" in self.endpoint_type.lower():
                return "dashscope"
            # 默认按 openai 兼容处理
            return "openai"
        host = self.api_host.lower()
        if "dashscope" in host or "aliyuncs" in host:
            return "dashscope"
        if "tei" in host:
            return "tei"
        return "openai"
