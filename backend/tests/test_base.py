"""
测试 base.py — AI 分析器基类（AIBase, AIAnalyzer, JSON 工具函数）

独立测试每个函数和类，Mock OpenAI 客户端。
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
# AIBase 测试
# ═══════════════════════════════════════════════════════════════════

class TestAIBase:
    def test_init_with_api_key_creates_client(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_openai = MagicMock()
        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_openai)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url + "/v1",
        )

        base = AIBase(api_key="sk-test", base_url="https://api.test.com", model="gpt-4")
        assert base.api_key == "sk-test"
        assert base.model == "gpt-4"
        assert base.enabled is True
        assert base.client is not None

    def test_init_without_api_key_disabled(self):
        from app.algorithm.base import AIBase

        base = AIBase()
        assert base.enabled is False
        assert base.client is None

    def test_is_available(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_openai = MagicMock()
        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_openai)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        assert base.is_available() is True

        base.client = None
        assert base.is_available() is False

    def test_init_failure_disables(self, monkeypatch):
        from app.algorithm.base import AIBase

        monkeypatch.setattr(
            "app.algorithm.base.OpenAI",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("init failed")),
        )

        base = AIBase(api_key="sk-test")
        assert base.enabled is False
        assert base.client is None

    def test_call_ai_disabled_returns_none(self):
        from app.algorithm.base import AIBase

        base = AIBase()
        result = base.call_ai("sys", "user")
        assert result is None

    def test_call_ai_success(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_choice = MagicMock()
        mock_choice.message.content = "AI response"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system prompt", "user prompt")
        assert result == {"content": "AI response"}

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "deepseek-chat"
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "system prompt"
        assert call_kwargs["messages"][1]["role"] == "user"
        assert call_kwargs["messages"][1]["content"] == "user prompt"

    def test_call_ai_json_mode(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({"score": 95})
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user", json_mode=True)
        assert result == {"score": 95}

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_call_ai_raw_mode(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_choice = MagicMock()
        mock_choice.message.content = "raw output"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user", raw=True)
        assert result == "raw output"

    def test_call_ai_retry_on_empty_response(self, monkeypatch):
        from app.algorithm.base import AIBase

        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            mock_choice = MagicMock()
            mock_choice.message.content = "" if call_count[0] < 2 else "finally got data"
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = side_effect

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user")
        assert call_count[0] == 2

    def test_call_ai_429_retry(self, monkeypatch):
        """429 限流错误应在 APIError 处理器中判断 status_code 并重试"""
        from app.algorithm.base import AIBase
        from openai import APIError

        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                err = APIError("rate limited", request=MagicMock(), body={})
                err.status_code = 429  # explicitly set for the getattr check
                raise err
            mock_choice = MagicMock()
            mock_choice.message.content = "ok"
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = side_effect

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user")
        assert call_count[0] == 2

    def test_call_ai_429_max_retries_exceeded(self, monkeypatch):
        """429 持续限流超过最大重试应返回 None"""
        from app.algorithm.base import AIBase
        from openai import APIError

        mock_client = MagicMock()

        def always_429(**kwargs):
            err = APIError("rate limited", request=MagicMock(), body={})
            err.status_code = 429
            raise err

        mock_client.chat.completions.create.side_effect = always_429

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user")
        assert result is None

    def test_call_ai_timeout_exception_caught_by_api_error_handler(self, monkeypatch):
        """APITimeoutError 是 APIError 的子类，被第一个 except 捕获后返回 None"""
        from app.algorithm.base import AIBase
        from openai import APITimeoutError

        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise APITimeoutError(request=MagicMock())
            mock_choice = MagicMock()
            mock_choice.message.content = "ok"
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = side_effect

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user")
        # APITimeoutError is caught by APIError handler (no status_code) → returns None
        assert result is None
        # Only 1 attempt because APIError handler doesn't retry by default
        assert call_count[0] == 1

    def test_call_ai_json_mode_non_dict_wraps_as_content(self, monkeypatch):
        """json_mode=True 但返回非 JSON 时，parse_ai_json 会包装为 {'content': ...} 字典"""
        from app.algorithm.base import AIBase

        mock_choice = MagicMock()
        mock_choice.message.content = "plain text, not json"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user", json_mode=True)
        # parse_ai_json wraps non-JSON as {"content": "plain text, not json"}
        # This IS a dict, so the json_mode retry doesn't trigger
        assert result == {"content": "plain text, not json"}

    def test_call_ai_max_tokens_passed(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        base.call_ai("system", "user", max_tokens=100)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 100

    def test_call_ai_api_error_returns_none(self, monkeypatch):
        from app.algorithm.base import AIBase
        from openai import APIError

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = APIError(
            "API error", request=MagicMock(), body={}
        )

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user")
        assert result is None

    def test_call_ai_exception_returns_none(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("Unexpected")

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = base.call_ai("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_ai_async_delegates(self, monkeypatch):
        from app.algorithm.base import AIBase

        mock_choice = MagicMock()
        mock_choice.message.content = "async result"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        monkeypatch.setattr("app.algorithm.base.OpenAI", lambda **kw: mock_client)
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url,
        )

        base = AIBase(api_key="sk-test")
        result = await base.call_ai_async("sys", "user", raw=True)
        assert result == "async result"


# ═══════════════════════════════════════════════════════════════════
# AIAnalyzer 测试
# ═══════════════════════════════════════════════════════════════════

class TestAIAnalyzer:
    def test_init_stores_ai(self):
        from app.algorithm.base import AIBase, AIAnalyzer

        base = AIBase()
        analyzer = AIAnalyzer(base)
        assert analyzer.ai is base

    def test_call_ai_delegates(self):
        from app.algorithm.base import AIBase, AIAnalyzer

        base = MagicMock(spec=AIBase)
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
        from app.algorithm.base import AIBase, AIAnalyzer

        base = MagicMock(spec=AIBase)
        base.call_ai_async = AsyncMock(return_value="async delegated")

        analyzer = AIAnalyzer(base)
        result = await analyzer.call_ai_async("sys", "user", json_mode=True)

        assert result == "async delegated"
        base.call_ai_async.assert_called_once_with(
            "sys", "user",
            temperature=0.3, max_tokens=None,
            logger_prefix="", raw=False, json_mode=True,
        )
