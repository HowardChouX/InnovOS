"""
独立 models 表 — 替代 model_providers.models JSON 列。

借鉴 CherryStudio：
- 每个模型独立行，支持 per-model 配置
- 与 registry (models.json) 配合：registry 提供基础数据，本表存用户覆盖
"""

MODELS_TABLE = "models"

MODELS_DDL = f"""
CREATE TABLE IF NOT EXISTS {MODELS_TABLE} (
    provider_id     TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    name            TEXT DEFAULT '',
    capabilities    TEXT DEFAULT '[]',      -- JSON array: ["chat", "embedding", ...]
    endpoint_types  TEXT DEFAULT '[]',      -- JSON array: ["openai-chat-completions", ...]
    context_window  INTEGER DEFAULT 0,
    max_output_tokens INTEGER DEFAULT 0,
    max_input_tokens  INTEGER DEFAULT 0,
    model_group     TEXT DEFAULT '',
    is_enabled      INTEGER DEFAULT 1,
    metadata        TEXT DEFAULT '{{}}',    -- JSON blob: pricing, ownedBy, etc.

    PRIMARY KEY (provider_id, model_id),
    FOREIGN KEY (provider_id) REFERENCES model_providers(provider_id) ON DELETE CASCADE
);
"""
