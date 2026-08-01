"""构建「模型列表端点」的候选 URL 列表。

参考 cc-switch `services/model_fetch.rs:build_models_url_candidates`。
不同供应商把 OpenAI 兼容的 `GET /v1/models` 端点放在不同的路径下：

- 标准：``{base}/v1/models``（硅基流动、OpenRouter、DeepSeek 等）
- 已含版本段：``{base}/v1/models`` 当 base 以 ``/v1`` 结尾
- 智谱 Coding Plan：base 是 ``.../paas/v4`` -> ``{base}/models``（不能再拼 /v1）
- Anthropic 兼容子路径：DeepSeek/Kimi/GLM/Bailian/Stepfun/Doubao 等官方
  供应商把 Anthropic 协议挂在 ``/anthropic``、``/api/anthropic``、``/apps/anthropic``
  等子路径下。``/v1/models`` 端点位于根域名而非子路径。

本模块输出**按优先级排好序**的候选 URL 列表，`fetch_remote_models`
按顺序尝试，遇到 404/405 才继续下一个候选；遇到其它状态码立即失败。
"""
from __future__ import annotations

# 按长度降序排列 - 长前缀必须先匹配，否则 `/anthropic` 会先把
# `/api/anthropic` 提前剥离掉，留下残缺的根路径。
_KNOWN_COMPAT_SUFFIXES: tuple[str, ...] = (
    "/api/claudecode",
    "/api/anthropic",
    "/apps/anthropic",
    "/api/coding",
    "/claudecode",
    "/anthropic",
    "/step_plan",
    "/coding",
    "/claude",
)


def _ends_with_version_segment(url: str) -> bool:
    """判断 URL 是否以 OpenAI 风格的版本段 ``/v{N}`` 结尾（``N`` 为一个或多个数字）。

    例如 ``/v1``、``/v4``、``/v10`` 都算；``/vX``、``/models`` 不算。
    """
    last = url.rstrip("/").rsplit("/", 1)[-1]
    if not last.startswith("v") or len(last) <= 1:
        return False
    return all(ch.isdigit() for ch in last[1:])


def _strip_compat_suffix(base_url: str) -> str | None:
    """若 baseURL 以任一已知兼容子路径结尾，返回剥离后的剩余部分。"""
    for suffix in _KNOWN_COMPAT_SUFFIXES:
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return None


def build_models_url_candidates(
    base_url: str,
    *,
    is_full_url: bool = False,
    models_url_override: str | None = None,
) -> list[str]:
    """构造「模型列表端点」的候选 URL 列表（已去重，按优先级排序）。

    参数:
        base_url: 供应商 API base URL（可为完整 chat URL 或 host root）
        is_full_url: ``True`` 时表示 ``base_url`` 本身是完整端点（如
            ``/v1/chat/completions``），需要先剥离到 ``/v1`` 再拼 ``/models``
        models_url_override: 精确覆写（部分供应商自定义端点）；非空时只返回它

    返回:
        候选 URL 列表。空 base_url 抛出 ``ValueError``。
    """
    if models_url_override and models_url_override.strip():
        return [models_url_override.strip()]

    trimmed = base_url.strip().rstrip("/")
    if not trimmed:
        raise ValueError("Base URL is empty")

    candidates: list[str] = []

    if is_full_url:
        # 完整 URL 模式：从 `.../v1/chat/completions` 还原到 `.../v1` 再拼 models
        v1_idx = trimmed.find("/v1/")
        if v1_idx >= 0:
            root = trimmed[:v1_idx]
            if root and "://" in root:
                candidates.append(f"{root}/v1/models")
        if not candidates:
            # 没找到 /v1/ 段就按最后一个 / 切，保留根域
            slash_idx = trimmed.rfind("/")
            if slash_idx > 0:
                root = trimmed[:slash_idx]
                scheme_idx = root.find("://")
                if "://" in root and scheme_idx + 3 < len(root):
                    candidates.append(f"{root}/v1/models")
        if not candidates:
            raise ValueError("Cannot derive models endpoint from full URL")
        return _dedupe(candidates)

    # baseURL 已以版本段 /v{N} 结尾（如 /v1、智谱 /api/coding/paas/v4），
    # OpenAI 惯例的模型端点是 {base}/models，不能再补 /v1
    # （否则 .../coding/paas/v4/v1/models -> 404）。
    if _ends_with_version_segment(trimmed):
        candidates.append(f"{trimmed}/models")
        # 版本段非 /v1 时，保留旧的 /v1/models 作为兜底次候选（正确路径已在前）。
        if not trimmed.endswith("/v1"):
            candidates.append(f"{trimmed}/v1/models")
    else:
        candidates.append(f"{trimmed}/v1/models")

    # 若 baseURL 命中已知 Anthropic 兼容子路径，剥离后缀再追加候选
    stripped = _strip_compat_suffix(trimmed)
    if stripped:
        root = stripped.rstrip("/")
        if root and "://" in root:
            candidates.append(f"{root}/v1/models")
            candidates.append(f"{root}/models")

    return _dedupe(candidates)


def _dedupe(urls: list[str]) -> list[str]:
    """保持首次出现顺序的线性去重（候选最多 3-4 条，不值得上 Set）。"""
    seen: list[str] = []
    for url in urls:
        if url not in seen:
            seen.append(url)
    return seen
