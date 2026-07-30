"""
OpenAI 兼容协议 adapter — 唯一封装 `openai.OpenAI(...)` 的地方。

所有 model protocol="openai" 的供应商(DeepSeek / SiliconFlow / 阿里 DashScope /
OpenAI / 智谱 / Moonshot / Ollama 等)都走这里。

设计:
- Adapter 实例**不持有**任何 api_key
- 每次 chat/embedding 调用临时构造 OpenAI client(用完即释放)
- 同步 API(后续可改为 AsyncOpenAI,但需先改造所有 call_ai 调用方)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter:
    """OpenAI 兼容协议 adapter。所有方法都是即用即构造 client。"""

    def _ensure_v1_url(self, host: str) -> str:
        """补齐 /v1 后缀。"""
        if host.endswith("/v1"):
            return host
        return host.rstrip("/") + "/v1"

    def _new_client(self, api_key: str, api_host: str, timeout: float) -> OpenAI:
        return OpenAI(
            api_key=api_key,
            base_url=self._ensure_v1_url(api_host),
            http_client=httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0)),
        )

    def chat(
        self,
        *,
        api_key: str,
        api_host: str,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        response_format: dict | None = None,
        timeout: float = 30.0,
    ) -> str:
        """同步 chat 调用,返 content 字符串。"""
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        client = self._new_client(api_key, api_host, timeout)
        resp = client.chat.completions.create(**kwargs)
        if not resp.choices:
            raise RuntimeError(f"AI response has no choices: {resp}")
        content = resp.choices[0].message.content
        if not content:
            raise RuntimeError("AI response content is empty")
        return content

    def embedding(
        self,
        *,
        api_key: str,
        api_host: str,
        model_id: str,
        texts: list[str],
        timeout: float = 30.0,
    ) -> list[list[float]]:
        """同步 embedding 调用,返向量列表。"""
        client = self._new_client(api_key, api_host, timeout)
        resp = client.embeddings.create(model=model_id, input=texts)
        return [item.embedding for item in resp.data]