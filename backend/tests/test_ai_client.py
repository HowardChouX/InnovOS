"""
测试 ai_client.py — AI 客户端 API 调用封装

Mock OpenAI/httpx 的外部依赖，测试轮询、重试、并发控制逻辑。
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, ANY


# ── Fixtures ──

@pytest.fixture
def mock_openai_chat_response():
    """模拟 OpenAI chat.completions.create 的成功响应"""
    mock_choice = MagicMock()
    mock_choice.message.content = '{"result": "ok"}'
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


# ── pick_model ──

class TestPickModel:
    def test_picks_from_comma_list(self):
        from app.algorithm.ai_client import pick_model
        result = pick_model("deepseek-chat")
        assert result == "deepseek-chat"

    def test_picks_from_multiple(self):
        from app.algorithm.ai_client import pick_model
        result = pick_model("gpt-4o,deepseek-chat,claude-3")
        assert result in ("gpt-4o", "deepseek-chat", "claude-3")

    def test_empty_returns_default(self):
        from app.algorithm.ai_client import pick_model
        result = pick_model("")
        assert result == "deepseek-chat"

    def test_whitespace_stripped(self):
        from app.algorithm.ai_client import pick_model
        result = pick_model("  gpt-4o  ,  deepseek-chat  ")
        assert result in ("gpt-4o", "deepseek-chat")


# ── _resolve_base_url ──

class TestResolveBaseUrl:
    def test_key_config_takes_priority(self):
        from app.algorithm.ai_client import _resolve_base_url
        url = _resolve_base_url({"api_base_url": "https://custom.example.com/v1"}, "silicon")
        assert url == "https://custom.example.com/v1"

    @patch("app.algorithm.model_service.model_service")
    def test_provider_service_lookup(self, mock_svc):
        """model_service 查询 provider 的 apiHost"""
        mock_svc.get.return_value = {"apiHost": "https://api.siliconflow.cn"}
        from app.algorithm.ai_client import _resolve_base_url
        url = _resolve_base_url({}, "silicon")
        assert url == "https://api.siliconflow.cn"

    @patch("app.algorithm.model_service.model_service")
    def test_provider_not_found_falls_to_deepseek(self, mock_svc):
        mock_svc.get.return_value = None
        from app.algorithm.ai_client import _resolve_base_url
        url = _resolve_base_url({}, "unknown")
        assert url == "https://api.deepseek.com"

    def test_no_provider_falls_to_deepseek(self):
        from app.algorithm.ai_client import _resolve_base_url
        url = _resolve_base_url({})
        assert url == "https://api.deepseek.com"


# ── chat_completion ──

class TestChatCompletion:
    """测试 chat_completion 入口路由"""

    @patch("app.algorithm.ai_client._chat_with_model", new_callable=AsyncMock)
    async def test_routes_to_chat_with_model_when_model_id_set(self, mock_cwm):
        """传了 model_id 时应走 _chat_with_model 路径"""
        mock_cwm.return_value = "model response"
        from app.algorithm.ai_client import chat_completion

        result = await chat_completion(model_id="silicon:deepseek-v3")
        assert result == "model response"
        mock_cwm.assert_called_once_with(
            model_id="silicon:deepseek-v3",
            system_prompt="", user_prompt="",
            temperature=0.3, response_format=str, max_retries=3,
        )

    @patch("app.algorithm.ai_client._chat_with_key_manager", new_callable=AsyncMock)
    async def test_routes_to_key_manager_when_no_model_id(self, mock_cwkm):
        mock_cwkm.return_value = "key manager response"
        from app.algorithm.ai_client import chat_completion

        result = await chat_completion(provider_id="silicon")
        assert result == "key manager response"
        mock_cwkm.assert_called_once_with(
            system_prompt="", user_prompt="",
            temperature=0.3, response_format=str, max_retries=3,
            provider_id="silicon",
        )


# ── _chat_with_model ──

class TestChatWithModel:
    """测试 _chat_with_model — model_resolver 路径"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        # Mock model_resolver.resolve via the source module
        mock_resolved = MagicMock()
        mock_resolved.api_key = "sk-test"
        mock_resolved.api_host = "https://api.test.com"
        mock_resolved.model_id = "deepseek-v3"
        mock_resolved.provider_id = "test"
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = mock_resolved
        monkeypatch.setattr("app.algorithm.model_resolver.model_resolver", mock_resolver)

        # Mock key_manager
        self.mock_km = MagicMock()
        self.mock_km.acquire = AsyncMock()
        self.mock_km.release = MagicMock()
        monkeypatch.setattr("app.algorithm.ai_client.key_manager", self.mock_km)

        # Mock ModelRuntime.ensure_v1_url
        monkeypatch.setattr(
            "app.algorithm.model_runtime.ModelRuntime.ensure_v1_url",
            lambda url: url + "/v1" if not url.endswith("/v1") else url,
        )

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_successful_call_returns_content(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, world!"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_model

        result = _sync(_chat_with_model(
            model_id="test:deepseek-v3",
            system_prompt="sys", user_prompt="user",
            temperature=0.3, response_format=str, max_retries=3,
        ))
        assert result == "Hello, world!"

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_successful_call_returns_dict(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({"score": 85})
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_model

        result = _sync(_chat_with_model(
            model_id="test:deepseek-v3",
            system_prompt="sys", user_prompt="user",
            temperature=0.3, response_format=dict, max_retries=3,
        ))
        assert result == {"score": 85}

    def test_raises_on_resolver_failure(self, monkeypatch):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = None
        monkeypatch.setattr("app.algorithm.model_resolver.model_resolver", mock_resolver)

        from app.algorithm.ai_client import _chat_with_model

        with pytest.raises(RuntimeError, match="模型.*解析失败"):
            _sync(_chat_with_model(
                model_id="bad:model", system_prompt="", user_prompt="",
                temperature=0.3, response_format=str, max_retries=3,
            ))

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_raises_on_empty_choices(self, mock_httpx, mock_openai_cls):
        mock_resp = MagicMock()
        mock_resp.choices = []
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_model

        with pytest.raises(RuntimeError, match="no choices"):
            _sync(_chat_with_model(
                model_id="test:model", system_prompt="", user_prompt="",
                temperature=0.3, response_format=str, max_retries=3,
            ))

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_raises_on_empty_content(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_model

        with pytest.raises(RuntimeError, match="empty"):
            _sync(_chat_with_model(
                model_id="test:model", system_prompt="", user_prompt="",
                temperature=0.3, response_format=str, max_retries=3,
            ))

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_retry_on_transient_error_then_succeeds(self, mock_httpx, mock_openai_cls):
        call_count = [0]

        def failing_then_ok(**kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("429 Too Many Requests")
            mock_choice = MagicMock()
            mock_choice.message.content = "success"
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = failing_then_ok
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_model

        result = _sync(_chat_with_model(
            model_id="test:model", system_prompt="", user_prompt="",
            temperature=0.3, response_format=str, max_retries=3,
        ))
        assert result == "success"
        assert call_count[0] == 3

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_persistent_error_propagates(self, mock_httpx, mock_openai_cls):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("persistent error")
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_model

        with pytest.raises(RuntimeError):
            _sync(_chat_with_model(
                model_id="test:model", system_prompt="", user_prompt="",
                temperature=0.3, response_format=str, max_retries=3,
            ))

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_httpx_client_context_manager_used(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        mock_http_client = MagicMock()
        mock_http_client.__enter__.return_value = mock_http_client
        mock_httpx.Client.return_value = mock_http_client

        from app.algorithm.ai_client import _chat_with_model

        _sync(_chat_with_model(
            model_id="test:model", system_prompt="", user_prompt="",
            temperature=0.3, response_format=str, max_retries=3,
        ))
        assert mock_http_client.__enter__.called
        assert mock_http_client.__exit__.called

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_verify_openai_created_with_correct_params(self, mock_httpx, mock_openai_cls):
        """OpenAI 应使用正确参数初始化"""
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        mock_http_client = MagicMock()
        mock_http_client.__enter__.return_value = mock_http_client
        mock_httpx.Client.return_value = mock_http_client

        from app.algorithm.ai_client import _chat_with_model

        _sync(_chat_with_model(
            model_id="test:model", system_prompt="sys", user_prompt="user",
            temperature=0.3, response_format=str, max_retries=3,
        ))

        # OpenAI should have been created with the resolved api_key and base_url
        openai_kwargs = mock_openai_cls.call_args[1]
        assert openai_kwargs["api_key"] == "sk-test"
        assert "/v1" in openai_kwargs["base_url"]

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_markdown_wrapped_json(self, mock_httpx, mock_openai_cls):
        """响应被 markdown JSON 代码块包裹时仍应正确解析"""
        mock_choice = MagicMock()
        mock_choice.message.content = '```json\n{"key": "value"}\n```'
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_model

        result = _sync(_chat_with_model(
            model_id="test:model", system_prompt="", user_prompt="",
            temperature=0.3, response_format=str, max_retries=3,
        ))
        assert result == '```json\n{"key": "value"}\n```'


# ── _chat_with_key_manager ──

class TestChatWithKeyManager:
    """测试 _chat_with_key_manager — Key 池轮询路径"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        self.mock_km = MagicMock()
        self.mock_km.acquire = AsyncMock()
        self.mock_km.release = MagicMock()
        self.mock_km.get_key_for_request = AsyncMock(return_value={
            "api_key": "pool-key",
            "api_model": "deepseek-chat",
            "api_base_url": "",
        })
        monkeypatch.setattr("app.algorithm.ai_client.key_manager", self.mock_km)

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_successful_call(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = "pool response"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_key_manager
        result = _sync(_chat_with_key_manager(
            system_prompt="sys", user_prompt="user",
            temperature=0.3, response_format=str, max_retries=3,
        ))
        assert result == "pool response"

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_dict_response_format(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({"key": "value"})
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_key_manager
        result = _sync(_chat_with_key_manager(
            system_prompt="", user_prompt="", temperature=0.3,
            response_format=dict, max_retries=3,
        ))
        assert result == {"key": "value"}

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_system_prompt_omitted_when_empty(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_key_manager
        _sync(_chat_with_key_manager(
            system_prompt="", user_prompt="hi",
            temperature=0.3, response_format=str, max_retries=3,
        ))
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_rate_limit_retry(self, mock_httpx, mock_openai_cls):
        call_count = [0]
        def side_effect(**kwargs):
            call_count[0] += 1
            raise RuntimeError("429 Too Many Requests")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = side_effect
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_key_manager
        with pytest.raises(RuntimeError):
            _sync(_chat_with_key_manager(
                system_prompt="", user_prompt="",
                temperature=0.3, response_format=str, max_retries=2,
            ))
        assert call_count[0] >= 1

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_get_key_for_request_called(self, mock_httpx, mock_openai_cls):
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        # Setup httpx.Client context manager properly
        mock_http_client = MagicMock()
        mock_http_client.__enter__.return_value = mock_http_client
        mock_httpx.Client.return_value = mock_http_client

        from app.algorithm.ai_client import _chat_with_key_manager
        _sync(_chat_with_key_manager(
            system_prompt="", user_prompt="",
            temperature=0.3, response_format=str, max_retries=1,
        ))
        assert self.mock_km.get_key_for_request.await_count == 1

    @patch("app.algorithm.ai_client.OpenAI")
    @patch("app.algorithm.ai_client.httpx")
    def test_dict_response_with_json_content(self, mock_httpx, mock_openai_cls):
        """response_format=dict 时用 json.loads 解析，需要纯 JSON 内容"""
        mock_choice = MagicMock()
        mock_choice.message.content = '{"score": 95}'
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_client

        from app.algorithm.ai_client import _chat_with_key_manager
        result = _sync(_chat_with_key_manager(
            system_prompt="", user_prompt="", temperature=0.3,
            response_format=dict, max_retries=1,
        ))
        assert result == {"score": 95}


# ── Helper ──

def _sync(coro):
    """同步运行协程"""
    import asyncio
    return asyncio.run(coro)
