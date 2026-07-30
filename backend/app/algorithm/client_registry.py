"""
模型客户端注册表 — 按 protocol 分发到具体 adapter。

当前只支持 OpenAI-compatible protocol,覆盖 SiliconFlow / DeepSeek /
阿里 DashScope / OpenAI / 智谱 / Moonshot / Ollama 等供应商。

未来如需支持 Anthropic native / Gemini native,在 REGISTRY 注册新 adapter。
"""

from __future__ import annotations

from typing import Any, Protocol


class ModelClient(Protocol):
    """模型客户端协议 — 所有 adapter 必须实现。"""

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
    ) -> Any:
        ...

    def embedding(
        self,
        *,
        api_key: str,
        api_host: str,
        model_id: str,
        texts: list[str],
        timeout: float = 30.0,
    ) -> list[list[float]]:
        ...


class AIClientRegistry:
    """单例注册表:protocol 字符串 → adapter 实例/类。"""

    _registry: dict[str, ModelClient] = {}

    @classmethod
    def register(cls, protocol: str, adapter: ModelClient) -> None:
        cls._registry[protocol] = adapter

    @classmethod
    def get(cls, protocol: str) -> ModelClient:
        try:
            return cls._registry[protocol]
        except KeyError as exc:
            raise NotImplementedError(
                f"protocol '{protocol}' not registered; "
                f"supported: {sorted(cls._registry.keys())}"
            ) from exc

    @classmethod
    def supported_protocols(cls) -> list[str]:
        return sorted(cls._registry.keys())


# ── 注册默认 adapter ──


def _register_defaults() -> None:
    from app.algorithm.clients.openai_compatible import OpenAICompatibleAdapter

    AIClientRegistry.register("openai", OpenAICompatibleAdapter())


_register_defaults()