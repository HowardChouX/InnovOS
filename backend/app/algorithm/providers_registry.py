"""
内置供应商注册表 — 参考 CherryStudio providers.ts

每个供应商包含：
- id: 唯一标识
- name: 显示名称
- protocol: 协议类型（openai/anthropic）
- api_host: API 端点
- models: 模型列表，每个模型为 {"id": str, "capabilities": list[str]}
- website/key_url/docs_url: 参考链接
- category: 分类（chinese/global/local）

能力常量（参考 CherryStudio MODEL_CAPABILITY）：
- "chat" — 对话模型
- "embedding" — 嵌入模型
- "rerank" — 重排模型
- "reasoning" — 推理模型
- "image-generation" — 图像生成
"""

import re

# ── 能力常量 ──
CAPABILITY_CHAT = "chat"
CAPABILITY_EMBEDDING = "embedding"
CAPABILITY_RERANK = "rerank"
CAPABILITY_REASONING = "reasoning"
CAPABILITY_IMAGE_GENERATION = "image-generation"
CAPABILITY_VISION = "vision"

# ── 正则推断（cherry-style fallback，兼容旧字符串格式） ──
EMBEDDING_REGEX = re.compile(
    r"(?:^text-|embed|bge-|bce-|e5-|LLM2Vec|retrieval|uae-|gte-|"
    r"jina-clip|jina-embeddings|voyage-|multilingual-e5)",
    re.I,
)
RERANK_REGEX = re.compile(
    r"(?:rerank|re-rank|cross-encoder|bge-reranker|bce-reranker|cohere.*rerank)",
    re.I,
)
REASONING_REGEX = re.compile(r"(?:reasoner|reasoning|deepseek-r1|o1-|o3-)", re.I)
VISION_REGEX = re.compile(
    r"(?:vision|ocr|vl$|vlm|multimodal|qwen2\.5-vl|qwen-vl|"
    r"deepseek-vl|deepseek-ocr|internvl|internlm-xcomposer|"
    r"cogvlm|glm-4v|minicpm-v|yi-vision)",
    re.I,
)


def infer_capabilities(model_id: str) -> list[str]:
    """从模型名称推断能力（cherry-style fallback）。

    当模型没有预设 capabilities 时（如 API 自动发现的模型、旧数据），
    通过模型名称的正则匹配来推断能力。
    """
    if RERANK_REGEX.search(model_id):
        return [CAPABILITY_RERANK]
    if EMBEDDING_REGEX.search(model_id):
        return [CAPABILITY_EMBEDDING]
    # 默认是聊天模型
    caps = [CAPABILITY_CHAT]
    if REASONING_REGEX.search(model_id):
        caps.append(CAPABILITY_REASONING)
    if VISION_REGEX.search(model_id):
        caps.append(CAPABILITY_VISION)
    return caps


def normalize_model(entry) -> dict:
    """统一模型格式：兼容 string 和 object 两种存储格式。

    旧格式: "gpt-4"
    新格式: {"id": "gpt-4", "capabilities": ["chat"]}
    """
    if isinstance(entry, str):
        return {"id": entry, "capabilities": infer_capabilities(entry)}
    if isinstance(entry, dict):
        entry.setdefault("capabilities", infer_capabilities(entry.get("id", "")))
        return entry
    return {"id": str(entry), "capabilities": ["chat"]}


def get_model_id(entry) -> str:
    """从 string 或 object 中获取模型 ID。"""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("id", "")
    return str(entry)


def get_model_capabilities(entry) -> list[str]:
    """从 string 或 object 中获取能力列表。"""
    return normalize_model(entry)["capabilities"]
