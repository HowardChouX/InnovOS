"""
内置供应商注册表 — 参考 CherryStudio providers.ts

每个供应商包含：
- id: 唯一标识
- name: 显示名称
- protocol: 协议类型（openai/anthropic）
- api_host: API 端点
- models: 预定义模型列表
- website/key_url/docs_url: 参考链接
- category: 分类（chinese/global/local）
"""

BUILTIN_PROVIDERS = {
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "protocol": "openai",
        "api_host": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "website": "https://deepseek.com/",
        "key_url": "https://platform.deepseek.com/api_keys",
        "docs_url": "https://platform.deepseek.com/api-docs/",
        "category": "chinese",
    },
    "silicon": {
        "id": "silicon",
        "name": "SiliconFlow",
        "protocol": "openai",
        "api_host": "https://api.siliconflow.cn",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "Qwen/Qwen2.5-72B-Instruct",
            "BAAI/bge-large-zh-v1.5",
        ],
        "website": "https://www.siliconflow.cn",
        "key_url": "https://cloud.siliconflow.cn",
        "category": "chinese",
    },
    "dashscope": {
        "id": "dashscope",
        "name": "阿里百炼",
        "protocol": "openai",
        "api_host": "https://dashscope.aliyuncs.com/compatible-mode/v1/",
        "models": ["qwen-turbo", "qwen-max", "qwen-plus", "text-embedding-v3"],
        "website": "https://www.aliyun.com/product/bailian",
        "key_url": "https://bailian.console.aliyun.com/#/api-key",
        "category": "chinese",
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "protocol": "openai",
        "api_host": "https://api.openai.com",
        "models": ["gpt-4o", "gpt-4o-mini", "o1-preview", "text-embedding-3-small"],
        "website": "https://openai.com/",
        "key_url": "https://platform.openai.com/api-keys",
        "docs_url": "https://platform.openai.com/docs",
        "category": "global",
    },
    "zhipu": {
        "id": "zhipu",
        "name": "智谱 AI",
        "protocol": "openai",
        "api_host": "https://open.bigmodel.cn/api/paas/v4/",
        "models": ["glm-4-plus", "glm-4-flash", "embedding-3"],
        "website": "https://open.bigmodel.cn/",
        "key_url": "https://open.bigmodel.cn/apikey/platform",
        "category": "chinese",
    },
    "moonshot": {
        "id": "moonshot",
        "name": "Moonshot AI",
        "protocol": "openai",
        "api_host": "https://api.moonshot.cn",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "website": "https://www.moonshot.cn/",
        "key_url": "https://platform.moonshot.cn/console/api-keys",
        "category": "chinese",
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama (本地)",
        "protocol": "openai",
        "api_host": "http://localhost:11434",
        "models": [],
        "website": "https://ollama.com/",
        "category": "local",
    },
}

# 常用 Embedding 模型（用于知识库 RAG）
EMBEDDING_MODELS = {
    "silicon": ["BAAI/bge-large-zh-v1.5", "BAAI/bge-m3"],
    "dashscope": ["text-embedding-v3", "text-embedding-v2"],
    "openai": ["text-embedding-3-small", "text-embedding-3-large"],
    "zhipu": ["embedding-3"],
}


def get_provider_info(provider_id: str) -> dict | None:
    """获取内置供应商信息。"""
    return BUILTIN_PROVIDERS.get(provider_id)


def list_all_builtin() -> list[dict]:
    """返回所有内置供应商列表。"""
    return list(BUILTIN_PROVIDERS.values())


def get_embedding_providers() -> list[dict]:
    """返回支持 Embedding 的供应商列表。"""
    result = []
    for pid, models in EMBEDDING_MODELS.items():
        if pid in BUILTIN_PROVIDERS:
            result.append({
                **BUILTIN_PROVIDERS[pid],
                "models": models,
            })
    return result
