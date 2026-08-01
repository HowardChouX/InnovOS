"""Tests for app.algorithm.model_url_builder — Python port of cc-switch build_models_url_candidates.

Covers every edge case from cc-switch's own test suite, plus a few extras
(空 base_url、纯根域、重复尾斜杠、缺省 None models_url_override)。
"""
from __future__ import annotations

import pytest

from app.algorithm.model_url_builder import build_models_url_candidates


class TestBuildCandidatesPlain:
    """纯根域名 / 末尾斜杠 / /v1 结尾的常规情况。"""

    def test_plain_root(self):
        c = build_models_url_candidates("https://api.siliconflow.cn")
        assert c == ["https://api.siliconflow.cn/v1/models"]

    def test_trailing_slash(self):
        c = build_models_url_candidates("https://api.example.com/")
        assert c == ["https://api.example.com/v1/models"]

    def test_with_v1(self):
        c = build_models_url_candidates("https://api.example.com/v1")
        assert c == ["https://api.example.com/v1/models"]

    def test_deduplicate_root(self):
        # 纯根域剥不出子路径 -> 1 个候选
        c = build_models_url_candidates("https://host.example.com")
        assert len(c) == 1

    def test_no_strip_for_plain_api(self):
        # /api 不是已知 compat 后缀,不剥离
        c = build_models_url_candidates("https://openrouter.ai/api")
        assert c == ["https://openrouter.ai/api/v1/models"]


class TestBuildCandidatesVersionSegments:
    """baseURL 已以版本段 /v{N} 结尾时(如智谱 Coding Plan 的 /v4)。"""

    def test_zhipu_coding_paas_v4(self):
        c = build_models_url_candidates("https://open.bigmodel.cn/api/coding/paas/v4")
        assert c == [
            "https://open.bigmodel.cn/api/coding/paas/v4/models",
            "https://open.bigmodel.cn/api/coding/paas/v4/v1/models",
        ]

    def test_zai_coding_paas_v4(self):
        c = build_models_url_candidates("https://api.z.ai/api/coding/paas/v4")
        assert c == [
            "https://api.z.ai/api/coding/paas/v4/models",
            "https://api.z.ai/api/coding/paas/v4/v1/models",
        ]

    def test_v10_is_version_segment(self):
        # /v10 也算版本段 - OpenAI 风格多版本路径要兼容。
        # 因为版本段非 /v1,同时保留 /v10/v1/models 作为兜底次候选。
        c = build_models_url_candidates("https://x.example/v10")
        assert c == [
            "https://x.example/v10/models",
            "https://x.example/v10/v1/models",
        ]


class TestBuildCandidatesAnthropicCompat:
    """Anthropic 协议挂在兼容子路径上时,需要剥离子路径找 /v1/models。"""

    def test_deepseek_anthropic(self):
        c = build_models_url_candidates("https://api.deepseek.com/anthropic")
        assert c == [
            "https://api.deepseek.com/anthropic/v1/models",
            "https://api.deepseek.com/v1/models",
            "https://api.deepseek.com/models",
        ]

    def test_zhipu_api_anthropic(self):
        c = build_models_url_candidates("https://open.bigmodel.cn/api/anthropic")
        assert c == [
            "https://open.bigmodel.cn/api/anthropic/v1/models",
            "https://open.bigmodel.cn/v1/models",
            "https://open.bigmodel.cn/models",
        ]

    def test_bailian_apps_anthropic(self):
        c = build_models_url_candidates("https://dashscope.aliyuncs.com/apps/anthropic")
        assert c == [
            "https://dashscope.aliyuncs.com/apps/anthropic/v1/models",
            "https://dashscope.aliyuncs.com/v1/models",
            "https://dashscope.aliyuncs.com/models",
        ]

    def test_stepfun_step_plan(self):
        c = build_models_url_candidates("https://api.stepfun.com/step_plan")
        assert c == [
            "https://api.stepfun.com/step_plan/v1/models",
            "https://api.stepfun.com/v1/models",
            "https://api.stepfun.com/models",
        ]

    def test_doubao_api_coding(self):
        c = build_models_url_candidates("https://ark.cn-beijing.volces.com/api/coding")
        assert c == [
            "https://ark.cn-beijing.volces.com/api/coding/v1/models",
            "https://ark.cn-beijing.volces.com/v1/models",
            "https://ark.cn-beijing.volces.com/models",
        ]

    def test_rightcode_claude(self):
        c = build_models_url_candidates("https://www.right.codes/claude")
        assert c == [
            "https://www.right.codes/claude/v1/models",
            "https://www.right.codes/v1/models",
            "https://www.right.codes/models",
        ]

    def test_longer_suffix_wins(self):
        # /api/anthropic 必须先匹配,不能被 /anthropic 提前吃掉
        c = build_models_url_candidates("https://api.z.ai/api/anthropic")
        assert c == [
            "https://api.z.ai/api/anthropic/v1/models",
            "https://api.z.ai/v1/models",
            "https://api.z.ai/models",
        ]

    def test_anthropic_version_segment_priority(self):
        # /api/anthropic/v1 先匹配版本段路径,v1/models 在前
        c = build_models_url_candidates("https://api.example.com/anthropic/v1")
        # _ends_with_version_segment 命中 -> {base}/models 首位
        assert c[0] == "https://api.example.com/anthropic/v1/models"


class TestBuildCandidatesFullUrl:
    """is_full_url 模式: baseURL 是 /v1/chat/completions 这类完整端点。"""

    def test_full_chat_url(self):
        c = build_models_url_candidates(
            "https://proxy.example.com/v1/chat/completions",
            is_full_url=True,
        )
        assert c == ["https://proxy.example.com/v1/models"]

    def test_full_url_no_v1_raises(self):
        # 没有 /v1/ 段也找不到根 -> ValueError
        with pytest.raises(ValueError, match="Cannot derive"):
            build_models_url_candidates("https://proxy.example.com", is_full_url=True)


class TestBuildCandidatesOverride:
    """models_url_override 精确覆写。"""

    def test_override_single(self):
        c = build_models_url_candidates(
            "https://api.deepseek.com/anthropic",
            models_url_override="https://api.deepseek.com/models",
        )
        assert c == ["https://api.deepseek.com/models"]

    def test_override_empty_falls_through(self):
        c = build_models_url_candidates(
            "https://api.siliconflow.cn",
            models_url_override="   ",
        )
        assert c == ["https://api.siliconflow.cn/v1/models"]

    def test_override_none_falls_through(self):
        c = build_models_url_candidates(
            "https://api.siliconflow.cn",
            models_url_override=None,
        )
        assert c == ["https://api.siliconflow.cn/v1/models"]


class TestBuildCandidatesInvalid:
    """输入校验。"""

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            build_models_url_candidates("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            build_models_url_candidates("   ")
