"""
测试 base.py — JSON 工具函数 + AIAnalyzer 分析器基类

AIBase 已移除（2026-08-01），测试只覆盖仍存在的 JSON 工具函数与 AIAnalyzer。
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ═══════════════════════════════════════════════════════════════════
# JSON 工具函数测试
# ═══════════════════════════════════════════════════════════════════

class TestStripThinkTags:
    def test_removes_think_tags(self):
        from app.algorithm.base import strip_think_tags
        result = strip_think_tags("before <think>hidden</think> after")
        assert result == "before  after"

    def test_removes_thinking_tags(self):
        from app.algorithm.base import strip_think_tags
        result = strip_think_tags("foo <thinking>bar</thinking> baz")
        assert result == "foo  baz"

    def test_removes_bracket_think(self):
        from app.algorithm.base import strip_think_tags
        result = strip_think_tags("a [thinking]b[/thinking] c")
        assert result == "a  c"

    def test_no_tags_unchanged(self):
        from app.algorithm.base import strip_think_tags
        result = strip_think_tags("hello world")
        assert result == "hello world"

    def test_normalizes_fullwidth_angle_brackets(self):
        from app.algorithm.base import strip_think_tags
        result = strip_think_tags("a ＜think＞b＜/think＞ c")
        assert result == "a  c"


class TestExtractJsonStr:
    def test_extracts_from_markdown_code_block(self):
        from app.algorithm.base import extract_json_str
        text = "Some text\n```json\n{\"key\": \"value\"}\n```\nmore"
        result = extract_json_str(text)
        assert result is not None
        assert json.loads(result) == {"key": "value"}

    def test_extracts_from_fence_without_lang(self):
        from app.algorithm.base import extract_json_str
        text = "```\n{\"a\": 1}\n```"
        result = extract_json_str(text)
        assert result is not None
        assert json.loads(result) == {"a": 1}

    def test_finds_first_brace_object(self):
        from app.algorithm.base import extract_json_str
        text = 'Here is the result: {"name": "test", "value": 42}'
        result = extract_json_str(text)
        assert result is not None
        assert json.loads(result) == {"name": "test", "value": 42}

    def test_none_for_empty_content(self):
        from app.algorithm.base import extract_json_str
        assert extract_json_str("") is None
        assert extract_json_str(None) is None  # type: ignore[arg-type]

    def test_removes_trailing_comma(self):
        from app.algorithm.base import extract_json_str
        text = '{"items": [1, 2, 3,]}'
        result = extract_json_str(text)
        assert result is not None
        assert json.loads(result) == {"items": [1, 2, 3]}

    def test_handles_no_json(self):
        from app.algorithm.base import extract_json_str
        result = extract_json_str("This is plain text with no JSON structure")
        assert result is None


class TestParseAiJson:
    def test_parses_dict_return(self):
        from app.algorithm.base import parse_ai_json
        result = parse_ai_json('{"score": 90}')
        assert result == {"score": 90}

    def test_strips_think_tags_first(self):
        from app.algorithm.base import parse_ai_json
        result = parse_ai_json("<think>思考中</think>{\"result\": true}")
        assert result == {"result": True}

    def test_returns_content_when_no_json(self):
        from app.algorithm.base import parse_ai_json
        result = parse_ai_json("plain text response")
        assert result == {"content": "plain text response"}

    def test_returns_none_for_empty(self):
        from app.algorithm.base import parse_ai_json
        assert parse_ai_json("") is None
        assert parse_ai_json(None) is None  # type: ignore[arg-type]


class TestRepairJson:
    def test_valid_json_returns_as_is(self):
        from app.algorithm.base import repair_json
        result = repair_json('{"a": 1}')
        assert result == '{"a": 1}'

    def test_closes_unclosed_brace(self):
        from app.algorithm.base import repair_json
        result = repair_json('{"a": {"b": 1}')
        assert result is not None
        parsed = json.loads(result)
        assert parsed == {"a": {"b": 1}}

    def test_none_for_empty(self):
        from app.algorithm.base import repair_json
        assert repair_json("") is None
        assert repair_json(None) is None  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════
# AIAnalyzer 测试
# ═══════════════════════════════════════════════════════════════════

class TestAIAnalyzer:
    def test_init_stores_ai(self):
        from app.algorithm.base import AIAnalyzer

        base = MagicMock()
        analyzer = AIAnalyzer(base)
        assert analyzer.ai is base

    def test_call_ai_delegates(self):
        from app.algorithm.base import AIAnalyzer

        base = MagicMock()
        base.call_ai.return_value = "delegated result"

        analyzer = AIAnalyzer(base)
        result = analyzer.call_ai("sys", "user", temperature=0.5, raw=True)

        assert result == "delegated result"
        base.call_ai.assert_called_once_with(
            "sys", "user",
            temperature=0.5, max_tokens=None,
            logger_prefix="", raw=True, json_mode=False,
        )

    @pytest.mark.asyncio
    async def test_call_ai_async_delegates(self):
        from app.algorithm.base import AIAnalyzer

        base = MagicMock()
        base.call_ai_async = AsyncMock(return_value="async delegated")

        analyzer = AIAnalyzer(base)
        result = await analyzer.call_ai_async("sys", "user", json_mode=True)

        assert result == "async delegated"
        base.call_ai_async.assert_called_once_with(
            "sys", "user",
            temperature=0.3, max_tokens=None,
            logger_prefix="", raw=False, json_mode=True,
        )
