# 视频生成多供应商重构 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将视频生成从 MiniMax 硬编码重构为 protocol 驱动的多供应商架构，同时落地 per-user 门控、动态参数下发、接入百炼 Wan 2.7

**Architecture:** `VideoAdapter` 抽象基类 + 注册表（`VideoRegistry`），按 `model_providers.protocol` 字段分发（`video_minimax` / `video_dashscope`）。adapter 内置 `capabilities()` 元数据驱动参数校验和前端渲染。`api/video.py` 通过门控查 `user_model_services` 队列取首个供应商，再走注册表取 adapter。

**Tech Stack:** Python 3.11+ / FastAPI / httpx / pytest / React 19 / TypeScript / Vitest

## Global Constraints

- `video_tasks.provider_id` 和 `video_tasks.model` 列已存在 — 零 schema 改动
- 聊天/嵌入路径不读 `model_providers.protocol`（`failover_router` 无引用，`model_runtime` 硬编码 `"openai"`），改 protocol 不影响文本功能
- `user_model_services` 已支持 `capability='video'`（`VALID_CAPABILITIES` 已含 `"video"`）
- `model_providers.protocol` 列已存在（默认 `'openai'`）
- 仅文生视频，不做图生/首尾帧/全能参考/音频/多镜头
- Wan 仅 2.7 系（`resolution`+`ratio` 参数模型），不支持 2.6 及更早的 `size`+`shot_type`
- 管理员页视频区块只读展示 adapter 能力，不做逐项收紧
- 不允许跨供应商 failover 自动重试
- 前端 `ApiError` 通过 `e.message` 获取中文错误提示（`extractError` 已处理）
- 前端的 `apiRequest` 对 403 不自动跳转（只处理 401 跳登录）

---

## 文件映射

| 文件                                                       | 操作     | 职责                                                                                                                                     |
| ---------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/algorithm/clients/video_base.py`              | **创建** | `VideoAdapter` 抽象基类 + `VideoRegistry` 注册表 + `VideoAdapterError`                                                                   |
| `backend/app/algorithm/clients/minimax_video.py`           | **修改** | 改为继承 `VideoAdapter`，重构 `create_task` 签名增加 `model` 参数，`query_task` 归一化状态，`MinimaxVideoError` 继承 `VideoAdapterError` |
| `backend/app/algorithm/clients/dashscope_video.py`         | **创建** | DashScope Wan 2.7 适配器，实现 `VideoAdapter`                                                                                            |
| `backend/app/algorithm/model_service.py`                   | **修改** | `upsert()` 增加 `protocol` 参数（白名单校验），`update()` 增加 `protocol` 可更新字段，`_row_to_dict` 增加 `protocol`                     |
| `backend/app/api/admin/providers.py`                       | **修改** | `AddProviderInput` 增加 `protocol` 字段，`UpdateProviderInput` 增加 `protocol` 字段，`add_provider` 透传 protocol                        |
| `backend/app/api/video.py`                                 | **修改** | 删除硬编码常量，新增门控/options/注册表分发                                                                                              |
| `backend/app/api/admin/user_model_services.py`             | **修改** | `_load()` 响应增加 `video_capabilities`，`_load_available()` 对 video 能力过滤 `protocol LIKE 'video_%'`                                 |
| `backend/app/services/video_task_service.py`               | **修改** | `create()` 增加 `provider_id`、`model` 参数                                                                                              |
| `backend/app/services/video_poller.py`                     | **修改** | 删除硬编码 minimax，按 provider_id 分组轮询                                                                                              |
| `frontend/src/api/admin/providers.ts`                      | **修改** | `Provider` 增加 `protocol`；`AddProviderInput` 增加 `protocol`；`UpdateProviderInput` 增加 `protocol`                                    |
| `frontend/src/api/admin/userModelServices.ts`              | **修改** | `UserModelService` 增加 `video_capabilities`                                                                                             |
| `frontend/src/api/video.ts`                                | **修改** | `GenerateInput` 去掉硬编码联合类型；新增 `VideoCapabilities`/`VideoOptions` 类型与 `videoApi.getOptions()`                               |
| `frontend/src/features/admin/ModelServiceForm.tsx`         | **修改** | 新增「协议」下拉                                                                                                                         |
| `frontend/src/features/admin/UserModelServicesPage.tsx`    | **修改** | `CAPABILITIES` 拆分 video/image；视频区块展示 `video_capabilities`                                                                       |
| `frontend/src/features/workflow/VideoDisplayPage.tsx`      | **修改** | 挂载时拉 options，动态渲染下拉，403 处理，去品牌化文案                                                                                   |
| `backend/tests/test_video_base.py`                         | **创建** | 注册表与 capabilities 测试                                                                                                               |
| `backend/tests/test_minimax_video_adapter.py`              | **修改** | 适配基类接口，增加状态归一化测试                                                                                                         |
| `backend/tests/test_dashscope_video_adapter.py`            | **创建** | DashScope 适配器全量测试                                                                                                                 |
| `backend/tests/test_video_api.py`                          | **修改** | 适配门控+注册表+options 新逻辑                                                                                                           |
| `backend/tests/test_video_poller.py`                       | **修改** | 适配按 provider_id 分组轮询                                                                                                              |
| `backend/tests/test_video_task_service.py`                 | **修改** | create 增加 provider_id+model 参数                                                                                                       |
| `backend/tests/test_admin_user_model_services.py`          | **修改** | 增加 video 能力过滤 + video_capabilities 断言                                                                                            |
| `frontend/src/features/admin/ModelServiceForm.test.tsx`    | **修改** | 增加 protocol 下拉测试                                                                                                                   |
| `frontend/src/features/workflow/VideoDisplayPage.test.tsx` | **创建** | 403 提示 + 动态渲染测试                                                                                                                  |

---

### Task 1: 抽象基类 + 注册表（`video_base.py`）

**Files:**

- Create: `backend/app/algorithm/clients/video_base.py`
- Test: `backend/tests/test_video_base.py`

**Interfaces:**

- Produces: `VideoAdapter`（ABC with `protocol: str`, `default_model: str`, `capabilities()`, `create_task()`, `query_task()`）, `VideoAdapterError(Exception)`, `VideoProtocolError(Exception)`, `VideoRegistry`（class with `register()`, `get()`）

- [ ] **Step 1: Write the failing test**

```python
"""VideoAdapter 基类 + 注册表测试。"""
import pytest
from app.algorithm.clients.video_base import (
    VideoAdapter,
    VideoAdapterError,
    VideoProtocolError,
    VideoRegistry,
)


class FakeAdapter(VideoAdapter):
    protocol = "video_fake"
    default_model = "fake-model"
    def capabilities(self):
        return {"resolutions": ["480P"], "duration": {"min": 2, "max": 10}, "ratios": ["16:9"]}
    async def create_task(self, **kwargs):
        return "fake-task-id"
    async def query_task(self, **kwargs):
        return {"status": "succeeded", "video_url": "https://x.mp4", "error": None}


def test_video_adapter_error_is_exception():
    assert issubclass(VideoAdapterError, Exception)


def test_video_protocol_error_is_exception():
    assert issubclass(VideoProtocolError, Exception)


def test_registry_register_and_get():
    VideoRegistry._registry = {}
    adapter = FakeAdapter()
    VideoRegistry.register(adapter)
    assert VideoRegistry.get("video_fake") is adapter


def test_registry_get_unknown_raises():
    VideoRegistry._registry = {}
    with pytest.raises(VideoProtocolError, match="video_unknown"):
        VideoRegistry.get("video_unknown")


def test_capabilities_structure():
    adapter = FakeAdapter()
    caps = adapter.capabilities()
    assert isinstance(caps["resolutions"], list)
    assert isinstance(caps["duration"], dict)
    assert "min" in caps["duration"] and "max" in caps["duration"]
    assert isinstance(caps["ratios"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_video_base.py -v`
Expected: FAIL with "ModuleNotFoundError" or "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
"""VideoAdapter 抽象基类 + 注册表。

所有视频供应商适配器继承此基类，通过 VideoRegistry 按 protocol 分发。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class VideoAdapterError(Exception):
    """所有视频 adapter 的统一异常，携带归一化错误信息。"""


class VideoProtocolError(Exception):
    """protocol 未注册。"""


class VideoAdapter(ABC):
    """视频适配器抽象基类。"""

    protocol: str = ""
    default_model: str = ""

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """返回能力元数据：{resolutions: list[str], duration: {min, max}, ratios: list[str]}。"""

    @abstractmethod
    async def create_task(
        self,
        *,
        api_key: str,
        api_host: str,
        model: str,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
    ) -> str:
        """创建文生视频任务，返回远端 task_id。"""

    @abstractmethod
    async def query_task(
        self,
        *,
        api_key: str,
        api_host: str,
        remote_task_id: str,
    ) -> dict[str, Any]:
        """查询并归一化状态。返回 {status, video_url, error}。
        status ∈ pending/queued/running/succeeded/failed。"""


class VideoRegistry:
    _registry: dict[str, VideoAdapter] = {}

    @classmethod
    def register(cls, adapter: VideoAdapter) -> None:
        cls._registry[adapter.protocol] = adapter
        logger.info("视频适配器已注册: protocol=%s", adapter.protocol)

    @classmethod
    def get(cls, protocol: str) -> VideoAdapter:
        adapter = cls._registry.get(protocol)
        if adapter is None:
            raise VideoProtocolError(
                f"不支持的视频协议: {protocol}；"
                f"已注册: {list(cls._registry.keys())}"
            )
        return adapter
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_video_base.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/algorithm/clients/video_base.py backend/tests/test_video_base.py
git commit -m "feat(video): VideoAdapter 抽象基类 + VideoRegistry 注册表"
```

---

### Task 2: 重构 MiniMax 适配器（继承 VideoAdapter）

**Files:**

- Modify: `backend/app/algorithm/clients/minimax_video.py`
- Test: `backend/tests/test_minimax_video_adapter.py`

**Interfaces:**

- Consumes: `VideoAdapter` (from Task 1), `VideoAdapterError` (from Task 1)
- Produces: `MinimaxVideoAdapter(VideoAdapter)` with `protocol='video_minimax'`, `default_model='MiniMax-H3'`

- [ ] **Step 1: Write the failing test**

```python
"""MiniMax 视频适配器测试 — 继承 VideoAdapter 基类。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.algorithm.clients.minimax_video import (
    MinimaxVideoAdapter,
    MinimaxVideoError,
)
from app.algorithm.clients.video_base import VideoAdapter, VideoAdapterError


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def adapter():
    return MinimaxVideoAdapter()


def test_adapter_is_video_adapter(adapter):
    assert isinstance(adapter, VideoAdapter)


def test_protocol_and_default_model(adapter):
    assert adapter.protocol == "video_minimax"
    assert adapter.default_model == "MiniMax-H3"


def test_capabilities(adapter):
    caps = adapter.capabilities()
    assert "768P" in caps["resolutions"]
    assert "2K" in caps["resolutions"]
    assert caps["duration"]["min"] == 4
    assert caps["duration"]["max"] == 15
    assert "16:9" in caps["ratios"]
    assert len(caps["ratios"]) == 6


def test_minimax_error_is_adapter_error():
    assert issubclass(MinimaxVideoError, VideoAdapterError)


async def test_create_task_passes_model(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"task_id": "424010985738629"})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        task_id = await adapter.create_task(
            api_key="sk-test",
            api_host="https://api.minimaxi.com",
            model="MiniMax-H3",
            prompt="一个男孩在海边打篮球",
            resolution="2K",
            duration=5,
            ratio="16:9",
        )

    assert task_id == "424010985738629"
    body = mock_client.post.call_args.kwargs["json"]
    assert body["model"] == "MiniMax-H3"


async def test_create_task_uses_custom_model(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"task_id": "x"})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        task_id = await adapter.create_task(
            api_key="sk-test",
            api_host="https://api.minimaxi.com",
            model="MiniMax-H3-20260901",
            prompt="test",
            resolution="768P",
            duration=5,
            ratio="16:9",
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["model"] == "MiniMax-H3-20260901"


async def test_query_task_cancelled_maps_to_failed(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"task": {"id": "x", "status": "cancelled"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
        )
    assert result["status"] == "failed"


async def test_query_task_expired_maps_to_failed(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"task": {"id": "x", "status": "expired"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
        )
    assert result["status"] == "failed"


async def test_query_task_non_terminal_maps_to_running(adapter):
    for s in ["queued", "processing", "pending"]:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=_mock_response(200, {"task": {"id": "x", "status": s}})
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.algorithm.clients.minimax_video.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await adapter.query_task(
                api_key="sk-test", api_host="https://api.minimaxi.com", remote_task_id="x"
            )
        assert result["status"] == "running", f"status {s} should map to running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_minimax_video_adapter.py -v`
Expected: FAIL — adapter not updated yet

- [ ] **Step 3: Write minimal implementation**

```python
"""MiniMax 视频生成 V2 适配器（Hailuo-03 / MiniMax-H3）。"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.algorithm.clients.video_base import VideoAdapter, VideoAdapterError

logger = logging.getLogger(__name__)


class MinimaxVideoError(VideoAdapterError):
    """MiniMax 接口返回非 2xx，携带其 error message。"""


class MinimaxVideoAdapter(VideoAdapter):
    protocol = "video_minimax"
    default_model = "MiniMax-H3"

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def capabilities(self) -> dict[str, Any]:
        return {
            "resolutions": ["768P", "2K"],
            "duration": {"min": 4, "max": 15},
            "ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
        }

    @staticmethod
    def _extract_error_message(data: Any, status_code: int) -> str:
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
        return f"MiniMax API error (HTTP {status_code})"

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return None

    async def create_task(
        self,
        *,
        api_key: str,
        api_host: str,
        model: str,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
    ) -> str:
        url = f"{api_host.rstrip('/')}/v2/video_generation"
        body = {
            "model": model,
            "content": [{"type": "text", "text": prompt}],
            "resolution": resolution,
            "duration": duration,
            "ratio": ratio,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
        data = self._safe_json(resp)
        if resp.status_code >= 400:
            raise MinimaxVideoError(
                self._extract_error_message(data, resp.status_code)
            )
        task_id = (data or {}).get("task_id") if isinstance(data, dict) else None
        if not task_id:
            raise MinimaxVideoError("MiniMax 未返回 task_id")
        return str(task_id)

    async def query_task(
        self,
        *,
        api_key: str,
        api_host: str,
        remote_task_id: str,
    ) -> dict[str, Any]:
        url = f"{api_host.rstrip('/')}/v2/query/video_generation/{remote_task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers)
        data = self._safe_json(resp)
        if resp.status_code >= 400:
            raise MinimaxVideoError(
                self._extract_error_message(data, resp.status_code)
            )
        task = (data or {}).get("task", {}) if isinstance(data, dict) else {}
        raw_status = task.get("status", "")
        # 归一化
        if raw_status == "succeeded":
            status = "succeeded"
        elif raw_status in ("failed", "cancelled", "expired"):
            status = "failed"
        else:
            status = "running"
        video_url = None
        if status == "succeeded":
            video_url = (task.get("content") or {}).get("url")
        error = task.get("error") if raw_status in ("failed", "expired") else None
        if error is not None and not isinstance(error, str):
            try:
                error = json.dumps(error, ensure_ascii=False)
            except (TypeError, ValueError):
                error = str(error)
        return {"status": status, "video_url": video_url, "error": error}


minimax_video_adapter = MinimaxVideoAdapter()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_minimax_video_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/algorithm/clients/minimax_video.py backend/tests/test_minimax_video_adapter.py
git commit -m "refactor(video): MiniMax adapter 继承 VideoAdapter，增加 model 参数与状态归一化"
```

---

### Task 3: DashScope Wan 2.7 适配器

**Files:**

- Create: `backend/app/algorithm/clients/dashscope_video.py`
- Test: `backend/tests/test_dashscope_video_adapter.py`

**Interfaces:**

- Consumes: `VideoAdapter` (Task 1), `VideoAdapterError` (Task 1)
- Produces: `DashScopeVideoAdapter(VideoAdapter)` with `protocol='video_dashscope'`, `default_model='wan2.7-t2v-2026-06-12'`

- [ ] **Step 1: Write the failing test**

```python
"""DashScope Wan 2.7 视频适配器测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.algorithm.clients.dashscope_video import (
    DashScopeVideoAdapter,
    DashScopeVideoError,
)
from app.algorithm.clients.video_base import VideoAdapter, VideoAdapterError


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def adapter():
    return DashScopeVideoAdapter()


def test_adapter_is_video_adapter(adapter):
    assert isinstance(adapter, VideoAdapter)


def test_protocol_and_default_model(adapter):
    assert adapter.protocol == "video_dashscope"
    assert adapter.default_model == "wan2.7-t2v-2026-06-12"


def test_capabilities(adapter):
    caps = adapter.capabilities()
    assert "480P" in caps["resolutions"]
    assert "720P" in caps["resolutions"]
    assert "1080P" in caps["resolutions"]
    assert caps["duration"]["min"] == 2
    assert caps["duration"]["max"] == 15
    assert "16:9" in caps["ratios"]
    assert "9:16" in caps["ratios"]
    assert len(caps["ratios"]) == 6


def test_error_is_adapter_error():
    assert issubclass(DashScopeVideoError, VideoAdapterError)


async def test_create_task_sends_correct_request(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_id": "tsk-123"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        task_id = await adapter.create_task(
            api_key="sk-ds",
            api_host="https://dashscope.aliyuncs.com/api/v1",
            model="wan2.7-t2v-2026-06-12",
            prompt="test video",
            resolution="720P",
            duration=10,
            ratio="16:9",
        )

    assert task_id == "tsk-123"
    call = mock_client.post.call_args
    assert call.args[0] == "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    headers = call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-ds"
    assert headers["X-DashScope-Async"] == "enable"
    body = call.kwargs["json"]
    assert body["model"] == "wan2.7-t2v-2026-06-12"
    assert body["input"]["prompt"] == "test video"
    assert body["parameters"]["resolution"] == "720P"
    assert body["parameters"]["ratio"] == "16:9"
    assert body["parameters"]["duration"] == 10
    assert body["parameters"]["prompt_extend"] is True
    assert body["parameters"]["watermark"] is False


async def test_create_task_with_custom_model(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_id": "tsk-456"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        task_id = await adapter.create_task(
            api_key="sk-ds",
            api_host="https://dashscope.aliyuncs.com/api/v1",
            model="wan2.7-t2v-20260901",
            prompt="test",
            resolution="1080P",
            duration=15,
            ratio="21:9",
        )
    assert task_id == "tsk-456"
    body = mock_client.post.call_args.kwargs["json"]
    assert body["model"] == "wan2.7-t2v-20260901"


async def test_create_task_normalizes_api_host(adapter):
    """api_host 已含 /api/v1 时不应重复拼接。"""
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_id": "x"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        await adapter.create_task(
            api_key="sk",
            api_host="https://dashscope.aliyuncs.com",
            model="wan2.7",
            prompt="x",
            resolution="720P",
            duration=5,
            ratio="16:9",
        )
    url = mock_client.post.call_args.args[0]
    assert url == "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"


async def test_query_task_pending_maps_to_queued(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_status": "PENDING"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "queued"


async def test_query_task_running(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"output": {"task_status": "RUNNING"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "running"


async def test_query_task_succeeded_returns_url(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {"output": {"task_status": "SUCCEEDED", "video_url": "https://cdn.x.com/out.mp4"}},
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "succeeded"
    assert result["video_url"] == "https://cdn.x.com/out.mp4"


async def test_query_task_failed_returns_error(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {
                "output": {
                    "task_status": "FAILED",
                    "message": "request rejected",
                    "code": "RateLimitExceeded",
                }
            },
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
            remote_task_id="tsk-1",
        )
    assert result["status"] == "failed"
    assert result["error"] is not None


def _mock_bad_json_response(status_code: int):
    import json as _json
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(side_effect=_json.JSONDecodeError("Expecting value", "", 0))
    return resp


async def test_create_task_html_502_raises_dashscope_error(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=_mock_bad_json_response(502))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(DashScopeVideoError) as exc:
            await adapter.create_task(
                api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
                model="wan2.7", prompt="x", resolution="720P", duration=5, ratio="16:9",
            )
    assert "502" in str(exc.value)


async def test_query_task_html_504_raises_dashscope_error(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=_mock_bad_json_response(504))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.dashscope_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(DashScopeVideoError) as exc:
            await adapter.query_task(
                api_key="sk", api_host="https://dashscope.aliyuncs.com/api/v1",
                remote_task_id="x",
            )
    assert "504" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_dashscope_video_adapter.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

```python
"""DashScope 百炼 Wan 2.7 文生视频适配器。

非 OpenAI 兼容协议，用 httpx 直打 REST。异步任务模型：
- create_task: POST .../services/aigc/video-generation/video-synthesis
               → {"output": {"task_id": ...}}
- query_task:  GET .../tasks/{task_id}
               → {"output": {"task_status": ..., "video_url": ...}}
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.algorithm.clients.video_base import VideoAdapter, VideoAdapterError

logger = logging.getLogger(__name__)

_API_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"
_TASK_PATH = "/api/v1/tasks"


class DashScopeVideoError(VideoAdapterError):
    """DashScope 接口返回非 2xx，携带其错误信息。"""


class DashScopeVideoAdapter(VideoAdapter):
    protocol = "video_dashscope"
    default_model = "wan2.7-t2v-2026-06-12"

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    def capabilities(self) -> dict[str, Any]:
        return {
            "resolutions": ["480P", "720P", "1080P"],
            "duration": {"min": 2, "max": 15},
            "ratios": ["16:9", "9:16", "4:3", "3:4", "1:1", "21:9"],
        }

    @staticmethod
    def _normalize_base(api_host: str) -> str:
        """确保 api_host 不含尾部 /api/v1（由拼接时统一加）。"""
        host = api_host.rstrip("/")
        if host.endswith("/api/v1"):
            host = host[: -len("/api/v1")]
        return host

    @staticmethod
    def _extract_error(data: Any, status_code: int) -> str:
        if isinstance(data, dict):
            msg = data.get("message") or ""
            code = data.get("code") or ""
            if msg and code:
                return f"{code}: {msg}"
            if msg:
                return str(msg)
        return f"DashScope API error (HTTP {status_code})"

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return None

    async def create_task(
        self,
        *,
        api_key: str,
        api_host: str,
        model: str,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
    ) -> str:
        base = self._normalize_base(api_host)
        url = f"{base}{_API_PATH}"
        body = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {
                "resolution": resolution,
                "ratio": ratio,
                "duration": duration,
                "prompt_extend": True,
                "watermark": False,
            },
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-Async": "enable",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
        data = self._safe_json(resp)
        if resp.status_code >= 400:
            raise DashScopeVideoError(
                self._extract_error(data, resp.status_code)
            )
        task_id = (data or {}).get("output", {}).get("task_id") if isinstance(data, dict) else None
        if not task_id:
            raise DashScopeVideoError("DashScope 未返回 task_id")
        return str(task_id)

    async def query_task(
        self,
        *,
        api_key: str,
        api_host: str,
        remote_task_id: str,
    ) -> dict[str, Any]:
        base = self._normalize_base(api_host)
        url = f"{base}{_TASK_PATH}/{remote_task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers)
        data = self._safe_json(resp)
        if resp.status_code >= 400:
            raise DashScopeVideoError(
                self._extract_error(data, resp.status_code)
            )
        output = (data or {}).get("output", {}) if isinstance(data, dict) else {}
        raw_status = (output.get("task_status") or "").upper()
        # 归一化
        STATUS_MAP = {
            "PENDING": "queued",
            "RUNNING": "running",
            "SUCCEEDED": "succeeded",
        }
        if raw_status in STATUS_MAP:
            status = STATUS_MAP[raw_status]
        else:
            status = "failed"
        video_url = output.get("video_url") if status == "succeeded" else None
        error = None
        if status == "failed":
            msg = output.get("message") or ""
            code = output.get("code") or ""
            error = f"{code}: {msg}" if code and msg else (msg or "unknown error")
        return {"status": status, "video_url": video_url, "error": error}


dashscope_video_adapter = DashScopeVideoAdapter()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_dashscope_video_adapter.py -v`
Expected: All PASS

- [ ] **Step 5: 注册两个 adapter 到 VideoRegistry + 回归验证**

在 `video_base.py` 底部添加延迟注册：

```python
# ── 注册内置视频适配器 ──
from app.algorithm.clients.minimax_video import minimax_video_adapter
from app.algorithm.clients.dashscope_video import dashscope_video_adapter

VideoRegistry.register(minimax_video_adapter)
VideoRegistry.register(dashscope_video_adapter)
```

Run: `cd backend && uv run pytest tests/test_video_base.py tests/test_minimax_video_adapter.py tests/test_dashscope_video_adapter.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/algorithm/clients/dashscope_video.py backend/tests/test_dashscope_video_adapter.py backend/app/algorithm/clients/video_base.py
git commit -m "feat(video): 新增 DashScope Wan 2.7 适配器 + 注册两个 adapter"
```

---

### Task 4: 后端 — model_service 支持 protocol 参数

**Files:**

- Modify: `backend/app/algorithm/model_service.py`
- Modify: `backend/app/api/admin/providers.py`
- Test: `backend/tests/test_model_service_api.py`

**Interfaces:**

- Consumes: `model_service.upsert()` now accepts `protocol: str = "openai"`; `model_service.update()` now accepts `protocol: str | None = None`
- Produces: `AddProviderInput.protocol: str = "openai"`, `UpdateProviderInput.protocol: str | None = None`

- [ ] **Step 1: Write the failing test**

```python
"""测试供应商创建/更新时 protocol 字段的透传。"""
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import providers as providers_mod
from app.auth import require_admin

app = FastAPI()
app.include_router(providers_mod.router, prefix="/api/admin")
app.dependency_overrides[require_admin] = lambda: {"id": 1, "role": "admin"}

client = TestClient(app)


def test_add_provider_with_protocol():
    with patch.object(providers_mod.model_service, "get", return_value=None), \
         patch.object(providers_mod.model_service, "upsert", return_value={
             "providerId": "test-video", "protocol": "video_minimax"
         }):
        resp = client.post("/api/admin/providers", json={
            "provider_id": "test-video",
            "name": "Test Video",
            "api_host": "https://api.test.com",
            "api_key": "sk-test",
            "protocol": "video_minimax",
        })
    assert resp.status_code == 200
    _, kwargs = providers_mod.model_service.upsert.call_args
    assert kwargs["protocol"] == "video_minimax"


def test_add_provider_defaults_to_openai():
    with patch.object(providers_mod.model_service, "get", return_value=None), \
         patch.object(providers_mod.model_service, "upsert", return_value={
             "providerId": "test", "protocol": "openai"
         }):
        resp = client.post("/api/admin/providers", json={
            "provider_id": "test",
            "name": "Test",
            "api_host": "https://api.test.com",
            "api_key": "sk-test",
        })
    assert resp.status_code == 200
    _, kwargs = providers_mod.model_service.upsert.call_args
    assert kwargs["protocol"] == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_model_service_api.py::test_add_provider_with_protocol -v`
Expected: FAIL

- [ ] **Step 3: Implement model_service.py changes**

在 `upsert()` 方法签名增加 `protocol` 参数，INSERT 使用该参数：

```python
def upsert(
    self,
    *,
    provider_id: str,
    name: str,
    notes: str = "",
    api_host: str,
    api_key_plaintext: str,
    api_model: str = "",
    protocol: str = "openai",
) -> dict[str, Any]:
    # ... 已有校验 ...
    VALID_PROTOCOLS = {"openai", "video_minimax", "video_dashscope"}
    if protocol not in VALID_PROTOCOLS:
        raise ValueError(f"invalid protocol: {protocol}")
    # ... 已有逻辑 ...
    if existing is None:
        db.execute(
            "INSERT INTO model_providers (provider_id, name, notes, api_host, "
            "api_model, protocol, models, max_rpm, is_enabled) "
            "VALUES (%s, %s, %s, %s, %s, %s, '[]', 60, 1)",
            (provider_id, name, notes or "", api_host, api_model or "", protocol),
        )
    else:
        db.execute(
            "UPDATE model_providers SET name=%s, notes=%s, api_host=%s, "
            "api_model=%s, protocol=%s WHERE provider_id=%s",
            (name, notes or "", api_host, api_model or "", protocol, provider_id),
        )
    # ...
```

在 `update()` 方法增加 `protocol` 参数：

```python
def update(
    self,
    provider_id: str,
    *,
    name: Optional[str] = None,
    notes: Optional[str] = None,
    api_host: Optional[str] = None,
    api_model: Optional[str] = None,
    is_enabled: Optional[bool] = None,
    protocol: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    # ... 已有逻辑 ...
    merged = {
        # ...
        "protocol": protocol if protocol is not None else current.get("protocol", "openai"),
    }
    # ... UPDATE SQL 增加 protocol 列 ...
```

在 `_row_to_dict` 增加 `protocol`：

```python
"protocol": d.get("protocol") or "openai",
```

- [ ] **Step 4: 修改 `backend/app/api/admin/providers.py`**

```python
class AddProviderInput(BaseModel):
    provider_id: str
    name: str
    notes: str = ""
    api_host: str
    api_key: str
    api_model: str = ""
    protocol: str = "openai"


class UpdateProviderInput(BaseModel):
    name: str | None = None
    notes: str | None = None
    api_host: str | None = None
    api_key: str | None = None
    api_model: str | None = None
    is_enabled: bool | None = None
    protocol: str | None = None
```

在 `add_provider` 调用 `upsert` 时透传 `protocol`：

```python
result = model_service.upsert(
    provider_id=body.provider_id,
    name=body.name,
    notes=body.notes,
    api_host=body.api_host,
    api_key_plaintext=body.api_key,
    api_model=body.api_model,
    protocol=body.protocol,
)
```

在 `update_provider` 增加 `protocol` 更新逻辑：

```python
if body.protocol is not None:
    update_kwargs["protocol"] = body.protocol
```

- [ ] **Step 5: Run tests to verify**

Run: `cd backend && uv run pytest tests/test_model_service_api.py::test_add_provider_with_protocol tests/test_model_service_api.py::test_add_provider_defaults_to_openai -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/algorithm/model_service.py backend/app/api/admin/providers.py
git commit -m "feat(admin): model_service 与 providers API 支持 protocol 字段"
```

---

### Task 5: 后端 — video.py 重构（门控 + 注册表 + options）

**Files:**

- Modify: `backend/app/api/video.py`
- Test: `backend/tests/test_video_api.py`

**Interfaces:**

- Consumes: `VideoRegistry.get()` (Task 1), `video_task_service.create()` (Task 6), `get_api_key_service()`
- Produces: `GET /api/video/options` → `{providerId, providerName, protocol, model, capabilities}`, `POST /api/video/generate` with dynamic validation

- [ ] **Step 1: Write the failing test**

```python
"""/api/video 路由测试 — 门控 + 注册表 + options。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import video as video_api
from app.auth import get_current_user
from app.algorithm.clients.video_base import VideoRegistry


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(video_api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "test"}
    with TestClient(app) as c:
        yield c


def test_options_returns_403_when_no_video_provider(client):
    """未开通视频能力 → 403。"""
    with patch.object(video_api, "_select_user_video_provider", return_value=None):
        resp = client.get("/api/video/options")
    assert resp.status_code == 403


def test_options_returns_capabilities(client):
    provider = {
        "provider_id": "minimax",
        "protocol": "video_minimax",
        "api_host": "https://api.minimaxi.com",
        "api_model": "MiniMax-H3",
    }
    adapter = VideoRegistry.get("video_minimax")
    with patch.object(video_api, "_select_user_video_provider", return_value=provider), \
         patch.object(video_api, "_lease_key", return_value="sk-test"):
        resp = client.get("/api/video/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["providerId"] == "minimax"
    assert data["protocol"] == "video_minimax"
    assert data["model"] == "MiniMax-H3"
    assert "capabilities" in data


def test_generate_403_when_no_video_provider(client):
    with patch.object(video_api, "_select_user_video_provider", return_value=None):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 403


def test_generate_rejects_invalid_resolution(client):
    provider = {
        "provider_id": "minimax",
        "protocol": "video_minimax",
        "api_host": "https://api.minimaxi.com",
        "api_model": "MiniMax-H3",
    }
    with patch.object(video_api, "_select_user_video_provider", return_value=provider), \
         patch.object(video_api, "_lease_key", return_value="sk-test"):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "4K", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 422


def test_generate_minimax_path(client):
    provider = {
        "provider_id": "minimax",
        "protocol": "video_minimax",
        "api_host": "https://api.minimaxi.com",
        "api_model": "MiniMax-H3",
    }
    created = {"id": "task-1", "status": "pending"}
    with patch.object(video_api, "_select_user_video_provider", return_value=provider), \
         patch.object(video_api, "_lease_key", return_value="sk-test"), \
         patch.object(video_api.video_task_service, "create", return_value=created), \
         patch.object(video_api.video_task_service, "set_remote_task"), \
         patch.object(video_api.video_task_service, "mark_failed"), \
         patch.object(
             VideoRegistry.get("video_minimax"),
             "create_task",
             new=AsyncMock(return_value="remote-123"),
         ):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["taskId"] == "task-1"


def test_generate_no_key_returns_error(client):
    provider = {
        "provider_id": "minimax",
        "protocol": "video_minimax",
        "api_host": "https://api.minimaxi.com",
        "api_model": "MiniMax-H3",
    }
    created = {"id": "task-1", "status": "pending"}
    with patch.object(video_api, "_select_user_video_provider", return_value=provider), \
         patch.object(video_api, "_lease_key", return_value=None), \
         patch.object(video_api.video_task_service, "create", return_value=created), \
         patch.object(video_api.video_task_service, "mark_failed"):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "test", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_video_api.py -v`
Expected: FAIL — old tests broken + new tests fail

- [ ] **Step 3: Write minimal implementation**

```python
"""视频生成 API — 多供应商协议驱动。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.algorithm.clients.video_base import (
    VideoAdapterError,
    VideoProtocolError,
    VideoRegistry,
)
from app.auth import get_current_user
from app.database import db_session
from app.services.api_key_service import get_api_key_service
from app.services.video_task_service import video_task_service

router = APIRouter(prefix="/api/video", tags=["video"])


class GenerateInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=7000)
    resolution: str = "768P"
    duration: int = Field(default=5, ge=1, le=60)
    ratio: str = "16:9"


def _select_user_video_provider(user_id: int) -> dict | None:
    """查用户开通的视频供应商队列，返回第一个可用的 provider 行（含 protocol/api_host/api_model）。"""
    with db_session() as db:
        row = db.execute(
            """
            SELECT ums.provider_id, mp.protocol, mp.api_host, mp.api_model
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            WHERE ums.user_id = ? AND ums.capability = 'video' AND ums.is_enabled = TRUE
            ORDER BY ums.failover_order ASC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def _lease_key(provider_id: str) -> str | None:
    """租用指定 provider 的密钥。"""
    svc = get_api_key_service()
    lease = svc.lease_key(provider_id=provider_id)
    return lease.plaintext if lease else None


@router.get("/options")
async def get_options(user: dict = Depends(get_current_user)):
    provider = _select_user_video_provider(user["id"])
    if not provider:
        raise HTTPException(status_code=403, detail="未开通视频生成服务，请联系管理员")
    try:
        adapter = VideoRegistry.get(provider["protocol"])
    except VideoProtocolError:
        raise HTTPException(status_code=400, detail=f"不支持的视频协议: {provider['protocol']}")
    capabilities = adapter.capabilities()
    model = provider["api_model"] or adapter.default_model
    return {
        "data": {
            "providerId": provider["provider_id"],
            "providerName": provider["provider_id"],
            "protocol": provider["protocol"],
            "model": model,
            "capabilities": capabilities,
        },
        "message": "success",
        "code": 200,
    }


@router.post("/generate")
async def generate(body: GenerateInput, user: dict = Depends(get_current_user)):
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="prompt 不能为空")

    provider = _select_user_video_provider(user["id"])
    if not provider:
        raise HTTPException(status_code=403, detail="未开通视频生成服务，请联系管理员")

    protocol = provider["protocol"]
    if not protocol.startswith("video_"):
        raise HTTPException(status_code=400, detail="该供应商不是视频模型服务，请联系管理员")

    try:
        adapter = VideoRegistry.get(protocol)
    except VideoProtocolError:
        raise HTTPException(status_code=400, detail=f"不支持的视频协议: {protocol}")

    caps = adapter.capabilities()
    if body.resolution not in caps["resolutions"]:
        raise HTTPException(
            status_code=422,
            detail=f"非法分辨率: {body.resolution}，允许值: {', '.join(caps['resolutions'])}",
        )
    if body.ratio not in caps["ratios"]:
        raise HTTPException(
            status_code=422,
            detail=f"非法宽高比: {body.ratio}，允许值: {', '.join(caps['ratios'])}",
        )
    if body.duration < caps["duration"]["min"] or body.duration > caps["duration"]["max"]:
        raise HTTPException(
            status_code=422,
            detail=f"非法时长: {body.duration}，允许范围: {caps['duration']['min']}-{caps['duration']['max']}",
        )

    model = provider["api_model"] or adapter.default_model
    task = video_task_service.create(
        user["id"],
        prompt=body.prompt.strip(),
        resolution=body.resolution,
        duration=body.duration,
        ratio=body.ratio,
        provider_id=provider["provider_id"],
        model=model,
    )

    api_key = _lease_key(provider["provider_id"])
    if not api_key:
        video_task_service.mark_failed(task["id"], "该视频供应商未配置密钥")
        raise HTTPException(status_code=400, detail="该视频供应商未配置密钥")

    try:
        remote_task_id = await adapter.create_task(
            api_key=api_key,
            api_host=provider["api_host"],
            model=model,
            prompt=body.prompt.strip(),
            resolution=body.resolution,
            duration=body.duration,
            ratio=body.ratio,
        )
        video_task_service.set_remote_task(task["id"], remote_task_id)
    except VideoAdapterError as exc:
        video_task_service.mark_failed(task["id"], str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        video_task_service.mark_failed(task["id"], f"创建视频任务失败: {exc}")
        raise HTTPException(status_code=500, detail="创建视频任务失败")

    return {"data": {"taskId": task["id"]}, "message": "success", "code": 200}


# ── tasks 相关端点保持不变 ──
@router.get("/tasks")
def list_tasks(user: dict = Depends(get_current_user)):
    data = video_task_service.list_by_user(user["id"])
    return {"data": data, "message": "success", "code": 200}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, user: dict = Depends(get_current_user)):
    task = video_task_service.get(task_id)
    if not task or task["userId"] != user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"data": task, "message": "success", "code": 200}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    deleted = video_task_service.delete(task_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "deleted", "code": 200}
```

- [ ] **Step 4: Run tests to verify**

Run: `cd backend && uv run pytest tests/test_video_api.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/video.py
git commit -m "refactor(video): video.py 门控+注册表分发+options，删除硬编码"
```

---

### Task 6: 后端 — video_task_service 增加 provider_id + model

**Files:**

- Modify: `backend/app/services/video_task_service.py`
- Test: `backend/tests/test_video_task_service.py`

**Interfaces:**

- Produces: `VideoTaskService.create(..., provider_id: str, model: str)`

- [ ] **Step 1: Write the failing test**

```python
"""测试 video_task_service.create 传入 provider_id 与 model。"""
from unittest.mock import patch

import pytest

from app.services import video_task_service as vts_mod
from app.services.video_task_service import video_task_service


def test_create_with_provider_and_model():
    """INSERT 应包含 provider_id 和 model 列。"""
    captured_sql = []
    captured_params = []

    def fake_execute(sql, params=None):
        captured_sql.append(sql)
        captured_params.append(params or ())
        class FakeCursor:
            def fetchone(self):
                return {
                    "id": "tid",
                    "user_id": 1, "provider_id": "minimax", "model": "MiniMax-H3",
                    "prompt": "x", "resolution": "768P", "duration": 5, "ratio": "16:9",
                    "remote_task_id": None, "status": "pending",
                    "video_url": None, "error": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
        return FakeCursor()

    with patch.object(vts_mod, "db_session") as mock_session:
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.execute = fake_execute
        mock_session.return_value = mock_ctx

        video_task_service.create(
            1, prompt="x", resolution="768P", duration=5, ratio="16:9",
            provider_id="minimax", model="MiniMax-H3",
        )

    # 验证 INSERT 包含 provider_id 和 model
    insert_sql = [s for s in captured_sql if s.strip().upper().startswith("INSERT")]
    assert insert_sql, "无 INSERT 语句"
    assert "provider_id" in insert_sql[0]
    assert "model" in insert_sql[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_video_task_service.py::test_create_with_provider_and_model -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
def create(
    self,
    user_id: int,
    *,
    prompt: str,
    resolution: str,
    duration: int,
    ratio: str,
    provider_id: str = "minimax",
    model: str = "MiniMax-H3",
) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    with db_session() as db:
        db.execute(
            "INSERT INTO video_tasks "
            "(id, user_id, prompt, resolution, duration, ratio, provider_id, model, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
            (task_id, user_id, prompt, resolution, duration, ratio, provider_id, model),
        )
        row = db.execute(
            "SELECT * FROM video_tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return _row_to_dict(row)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_video_task_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/video_task_service.py
git commit -m "feat(video): video_task_service.create 增加 provider_id 与 model 参数"
```

---

### Task 7: 后端 — video_poller 按 provider_id 分组轮询

**Files:**

- Modify: `backend/app/services/video_poller.py`
- Test: `backend/tests/test_video_poller.py`

- [ ] **Step 1: Write the failing test**

```python
"""测试多供应商分组轮询。"""
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import video_poller as vp_mod
from app.services.video_poller import VideoPoller


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_poll_once_groups_by_provider_id():
    """两个不同 provider 的任务应分别 lease 各自的 key 并调用各自 adapter。"""
    poller = VideoPoller(interval_seconds=5)
    active = [
        {"id": "t1", "remoteTaskId": "r1", "providerId": "minimax"},
        {"id": "t2", "remoteTaskId": "r2", "providerId": "bailian"},
    ]
    query_results = {
        "r1": {"status": "succeeded", "video_url": "https://x/1.mp4", "error": None},
        "r2": {"status": "running", "video_url": None, "error": None},
    }

    # 模拟 _lease_key 按 provider_id 返回不同密钥
    lease_results = {"minimax": "sk-mm", "bailian": "sk-bl"}
    _original_lease = vp_mod._lease_key

    def mock_lease(provider_id):
        return lease_results.get(provider_id)

    # 模拟 _read_provider_row 返回对应行
    provider_rows = {
        "minimax": {"protocol": "video_minimax", "api_host": "https://api.minimaxi.com"},
        "bailian": {"protocol": "video_dashscope", "api_host": "https://dashscope.aliyuncs.com/api/v1"},
    }

    def mock_read(provider_id):
        return provider_rows.get(provider_id)

    # 模拟 adapter query_task
    async def mock_query(adapter_protocol, **kwargs):
        remote_id = kwargs["remote_task_id"]
        return query_results[remote_id]

    # 直接从注册表拿真实 adapter，但 mock 它们的 query_task
    from app.algorithm.clients.video_base import VideoRegistry
    minimax_adapter = VideoRegistry.get("video_minimax")
    dashscope_adapter = VideoRegistry.get("video_dashscope")

    with patch.object(vp_mod, "_lease_key", side_effect=mock_lease), \
         patch.object(vp_mod, "_read_provider_row", side_effect=mock_read), \
         patch.object(vp_mod.video_task_service, "list_active", return_value=active), \
         patch.object(vp_mod.video_task_service, "apply_remote_status") as mock_apply, \
         patch.object(minimax_adapter, "query_task", new=AsyncMock(return_value=query_results["r1"])), \
         patch.object(dashscope_adapter, "query_task", new=AsyncMock(return_value=query_results["r2"])):
        _run(poller.poll_once())

    assert mock_apply.call_count == 2


def test_poll_once_skips_group_without_key():
    """某 provider 无密钥时只跳过该组，不影响其他组。"""
    poller = VideoPoller(interval_seconds=5)
    active = [
        {"id": "t1", "remoteTaskId": "r1", "providerId": "minimax"},
        {"id": "t2", "remoteTaskId": "r2", "providerId": "no-key-provider"},
    ]

    def mock_lease(provider_id):
        return "sk" if provider_id == "minimax" else None

    def mock_read(provider_id):
        return {"protocol": "video_minimax", "api_host": "https://api.minimaxi.com"}

    from app.algorithm.clients.video_base import VideoRegistry
    minimax_adapter = VideoRegistry.get("video_minimax")

    with patch.object(vp_mod, "_lease_key", side_effect=mock_lease), \
         patch.object(vp_mod, "_read_provider_row", side_effect=mock_read), \
         patch.object(vp_mod.video_task_service, "list_active", return_value=active), \
         patch.object(vp_mod.video_task_service, "apply_remote_status") as mock_apply, \
         patch.object(minimax_adapter, "query_task", new=AsyncMock(return_value={"status": "succeeded", "video_url": "x", "error": None})):
        _run(poller.poll_once())

    # 只有 minimax 组的任务被回写
    assert mock_apply.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_video_poller.py -v`
Expected: FAIL

- [ ] **Step 3: Implement poller 重构**

```python
"""后台视频任务轮询器 — 多供应商分组轮询。"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.algorithm.clients.video_base import VideoProtocolError, VideoRegistry
from app.services.video_task_service import video_task_service

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"succeeded", "failed", "expired"}
STALE_PENDING_THRESHOLD = timedelta(minutes=10)


def _lease_key(provider_id: str) -> str | None:
    from app.database import db_session
    from app.services.api_key_service import get_api_key_service
    svc = get_api_key_service()
    lease = svc.lease_key(provider_id=provider_id)
    return lease.plaintext if lease else None


def _read_provider_row(provider_id: str) -> dict | None:
    """读取 model_providers 的 protocol 和 api_host。"""
    from app.database import db_session
    with db_session() as db:
        row = db.execute(
            "SELECT protocol, api_host FROM model_providers WHERE provider_id = ?",
            (provider_id,),
        ).fetchone()
    return dict(row) if row else None


def _is_stale_pending(task: dict) -> bool:
    created_at = task.get("createdAt")
    if not created_at:
        return True
    try:
        created = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created > STALE_PENDING_THRESHOLD


class VideoPoller:
    def __init__(self, interval_seconds: float = 5.0) -> None:
        self._interval = interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("视频轮询器已启动 (interval=%.1fs)", self._interval)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        logger.info("视频轮询器已停止")

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except Exception as exc:
                logger.warning(f"视频轮询轮次异常: {exc}")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    async def poll_once(self) -> int:
        active = video_task_service.list_active()
        if not active:
            return 0

        # 孤儿回收
        to_query = []
        count = 0
        for task in active:
            if not task.get("remoteTaskId"):
                if _is_stale_pending(task):
                    video_task_service.mark_failed(
                        task["id"], "任务创建超时：未关联远端任务，已自动标记失败",
                    )
                    count += 1
                continue
            to_query.append(task)

        if not to_query:
            return count

        # 按 provider_id 分组
        groups: dict[str, list[dict]] = defaultdict(list)
        for task in to_query:
            groups[task.get("providerId", "unknown")].append(task)

        for provider_id, tasks in groups.items():
            api_key = _lease_key(provider_id)
            if not api_key:
                logger.debug("供应商 %s 无密钥，跳过该组", provider_id)
                continue

            provider_row = _read_provider_row(provider_id)
            if not provider_row:
                logger.debug("供应商 %s 不存在，跳过该组", provider_id)
                continue

            try:
                adapter = VideoRegistry.get(provider_row["protocol"])
            except VideoProtocolError:
                logger.debug("供应商 %s 协议 %s 未注册，跳过该组",
                             provider_id, provider_row.get("protocol"))
                continue

            api_host = provider_row["api_host"]
            for task in tasks:
                remote_id = task["remoteTaskId"]
                try:
                    result = await adapter.query_task(
                        api_key=api_key, api_host=api_host, remote_task_id=remote_id,
                    )
                except Exception as exc:
                    logger.warning(f"查询任务 {task['id']} 失败: {exc}")
                    continue
                video_task_service.apply_remote_status(
                    task["id"],
                    status=result["status"],
                    video_url=result["video_url"],
                    error=result["error"],
                )
                count += 1
        return count


video_poller = VideoPoller()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_video_poller.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/video_poller.py
git commit -m "refactor(video): poller 按 provider_id 分组轮询，支持多供应商"
```

---

### Task 8: 后端 — admin user_model_services 增加 video_capabilities + 过滤

**Files:**

- Modify: `backend/app/api/admin/user_model_services.py`
- Test: `backend/tests/test_admin_user_model_services.py`

- [ ] **Step 1: Write the failing test**

```python
"""测试 admin user_model_services video 能力过滤与 video_capabilities。"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import user_model_services as ums_mod
from app.auth import require_admin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ums_mod.router, prefix="/api/admin/users/{user_id}/model-services")
    app.dependency_overrides[require_admin] = lambda: {"id": 1, "role": "admin"}
    with TestClient(app) as c:
        yield c


def test_available_video_filters_protocol():
    """video 能力只返回 protocol 以 video_ 开头的供应商。"""
    rows = [
        {"provider_id": "minimax", "name": "MiniMax", "api_host": "x", "api_model": "",
         "is_healthy": True, "already_enabled": False},
        {"provider_id": "bailian", "name": "百炼", "api_host": "x", "api_model": "",
         "is_healthy": True, "already_enabled": False},
        {"provider_id": "deepseek", "name": "DeepSeek", "api_host": "x", "api_model": "",
         "is_healthy": True, "already_enabled": False},
    ]

    def mock_db_execute(sql, params=None):
        # 检查 WHERE 子句是否包含 protocol LIKE
        if "protocol" in sql and "LIKE" in sql:
            assert "video_" in sql  # 应有 video_ 过滤
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        return cursor

    with patch("app.api.admin.user_model_services.get_db") as mock_get_db:
        mock_conn = MagicMock()
        mock_conn.execute = mock_db_execute
        mock_get_db.return_value = mock_conn
        resp = client.get("/api/admin/users/1/model-services/available?capability=video")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_admin_user_model_services.py::test_available_video_filters_protocol -v`
Expected: FAIL

- [ ] **Step 3: Implement**

修改 `_load_available()`：当 `capability == 'video'` 时，SQL 增加 `AND mp.protocol LIKE 'video_%'`：

```python
def _load_available(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    db = get_db()
    try:
        protocol_filter = ""
        params = [user_id, capability]
        if capability == "video":
            protocol_filter = " AND mp.protocol LIKE 'video_%'"
        rows = db.execute(
            f"""
            SELECT
                mp.provider_id,
                mp.name,
                mp.api_host,
                mp.api_model,
                COALESCE(ph.is_healthy, TRUE) AS is_healthy,
                EXISTS (
                    SELECT 1 FROM user_model_services ums2
                    WHERE ums2.user_id = %s
                      AND ums2.provider_id = mp.provider_id
                      AND ums2.capability = %s
                ) AS already_enabled
            FROM model_providers mp
            LEFT JOIN provider_health ph ON ph.provider_id = mp.provider_id
            WHERE mp.is_enabled = TRUE{protocol_filter}
            ORDER BY mp.name ASC
            """,
            tuple(params),
        ).fetchall()
    finally:
        db.close()
    return [_row_to_dict(r) for r in rows]
```

修改 `_load()`：对 `video_*` 协议的行计算 `video_capabilities`：

```python
def _load(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
                ums.capability,
                ums.failover_order,
                ums.is_enabled,
                mp.name,
                mp.api_host,
                mp.api_model,
                mp.protocol,
                COALESCE(ph.is_healthy, TRUE) AS is_healthy,
                COALESCE(ph.consecutive_failures, 0) AS consecutive_failures,
                ph.cooldown_until
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            LEFT JOIN provider_health ph ON ph.provider_id = ums.provider_id
            WHERE ums.user_id = %s AND ums.capability = %s
            ORDER BY ums.failover_order ASC
            """,
            (user_id, capability),
        ).fetchall()
    finally:
        db.close()
    result = [_row_to_dict(r) for r in rows]
    # 对 video 能力计算 video_capabilities
    if capability == "video":
        from app.algorithm.clients.video_base import VideoRegistry
        for item in result:
            protocol = item.get("protocol", "")
            if protocol.startswith("video_"):
                try:
                    adapter = VideoRegistry.get(protocol)
                    item["video_capabilities"] = adapter.capabilities()
                except Exception:
                    item["video_capabilities"] = None
            else:
                item["video_capabilities"] = None
    return result
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_admin_user_model_services.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin/user_model_services.py
git commit -m "feat(admin): user_model_services video 过滤 + video_capabilities 展示"
```

---

### Task 9: 前端 — API 类型更新（video.ts + providers.ts + userModelServices.ts）

**Files:**

- Modify: `frontend/src/api/video.ts`
- Modify: `frontend/src/api/admin/providers.ts`
- Modify: `frontend/src/api/admin/userModelServices.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { describe, it, expect } from 'vitest';

// 只验证类型可编译（通过 ts 检查）
describe('API types', () => {
  it('GenerateInput accepts any string for resolution/ratio', () => {
    // 编译时验证：如果 types 还是硬编码联合类型，这里会报错
    const input: import('../api/video').GenerateInput = {
      prompt: 'test',
      resolution: '720P', // 以前必须是 '768P' | '2K'
      duration: 5,
      ratio: '21:9', // 以前必须是 '21:9' | ...
    };
    expect(input.resolution).toBe('720P');
  });
});
```

- [ ] **Step 2: 实现前端类型更新**

```typescript
// frontend/src/api/video.ts
export interface GenerateInput {
  prompt: string;
  resolution: string;
  duration: number;
  ratio: string;
}

export interface VideoCapabilities {
  resolutions: string[];
  duration: { min: number; max: number };
  ratios: string[];
}

export interface VideoOptions {
  providerId: string;
  providerName: string;
  protocol: string;
  model: string;
  capabilities: VideoCapabilities;
}

export const videoApi = {
  // ... 已有方法 ...
  getOptions(): Promise<{ data: VideoOptions; message?: string; code: number }> {
    return apiRequest('/api/video/options');
  },
};
```

```typescript
// frontend/src/api/admin/providers.ts
export interface Provider {
  providerId: string;
  name: string;
  notes: string;
  apiHost: string;
  apiModel: string;
  isEnabled: boolean;
  protocol: string; // 新增
  health?: ProviderHealth;
  createdAt?: string;
  updatedAt?: string;
}

export interface AddProviderInput {
  provider_id: string;
  name: string;
  notes?: string;
  api_host: string;
  api_key: string;
  api_model?: string;
  protocol?: string; // 新增
}

export interface UpdateProviderInput {
  name?: string;
  notes?: string;
  api_host?: string;
  api_key?: string;
  api_model?: string;
  is_enabled?: boolean;
  protocol?: string; // 新增
}
```

```typescript
// frontend/src/api/admin/userModelServices.ts
export interface UserModelService {
  provider_id: string;
  capability: string;
  name: string;
  api_host: string;
  api_model: string;
  failover_order: number;
  is_enabled: boolean;
  is_healthy?: boolean;
  consecutive_failures?: number;
  cooldown_until?: string | null;
  video_capabilities?: VideoCapabilities | null; // 新增
  protocol?: string; // 新增
}

import type { VideoCapabilities } from '../video'; // 顶部增加
```

- [ ] **Step 3: 验证 TS 编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/video.ts frontend/src/api/admin/providers.ts frontend/src/api/admin/userModelServices.ts
git commit -m "feat(frontend): API 类型增加 protocol/video_capabilities/options"
```

---

### Task 10: 前端 — ModelServiceForm 增加协议下拉

**Files:**

- Modify: `frontend/src/features/admin/ModelServiceForm.tsx`
- Test: `frontend/src/features/admin/ModelServiceForm.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ModelServiceForm } from './ModelServiceForm';

vi.mock('../../api/admin/providers', () => ({
  providersApi: {
    detect: vi.fn().mockResolvedValue({
      data: { models: [{ id: 'gpt-4o-mini', name: 'gpt-4o-mini' }] },
    }),
    add: vi.fn().mockResolvedValue({ data: {} }),
    update: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

describe('ModelServiceForm protocol', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders protocol dropdown with video options', () => {
    render(<ModelServiceForm open mode="add" onClose={() => {}} onSave={() => {}} />);
    expect(screen.getByText('openai（文本/通用）')).toBeInTheDocument();
    expect(screen.getByText('video_minimax（MiniMax 视频）')).toBeInTheDocument();
    expect(screen.getByText('video_dashscope（百炼 Wan 视频）')).toBeInTheDocument();
  });

  it('submits protocol with add request', async () => {
    const { providersApi } = await import('../../api/admin/providers');
    const onSave = vi.fn();
    render(<ModelServiceForm open mode="add" onClose={() => {}} onSave={onSave} />);

    fireEvent.change(screen.getByPlaceholderText('例如 my-deepseek'), { target: { value: 'my-video' } });
    fireEvent.change(screen.getByPlaceholderText('DeepSeek (生产)'), { target: { value: 'My Video' } });
    fireEvent.change(screen.getByPlaceholderText('https://api.example.com/v1'), { target: { value: 'https://api.test.com' } });
    fireEvent.change(screen.getByPlaceholderText('sk-...'), { target: { value: 'sk-test' } });

    // 选择 video_minimax
    fireEvent.change(screen.getByDisplayValue('openai（文本/通用）'), { target: { value: 'video_minimax' } });

    fireEvent.click(screen.getByText('保存'));
    await waitFor(() => {
      expect(providersApi.add).toHaveBeenCalledWith(
        expect.objectContaining({ protocol: 'video_minimax' })
      );
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run --reporter=verbose src/features/admin/ModelServiceForm.test.tsx`
Expected: FAIL

- [ ] **Step 3: 在表单中添加协议下拉**

在 "默认模型" 字段上方添加协议下拉：

```tsx
const [protocol, setProtocol] = useState(initial?.protocol ?? 'openai');

// 在 useEffect reset 中增加：
setProtocol(initial?.protocol ?? 'openai');

// 在 handleSave 的 add 调用中增加 protocol：
if (mode === 'add') {
  await providersApi.add({
    provider_id: providerId.trim(),
    name: name.trim(),
    notes: notes.trim(),
    api_host: apiHost.trim(),
    api_key: apiKey,
    api_model: apiModel.trim(),
    protocol: protocol,
  });
}

// 在表单中增加协议行（在默认模型之后、按钮之前）：
<div>
  <label style={labelStyle}>协议</label>
  <select
    style={inputStyle}
    value={protocol}
    onChange={(e) => setProtocol(e.target.value)}
    name="innovos_protocol"
  >
    <option value="openai">openai（文本/通用）</option>
    <option value="video_minimax">video_minimax（MiniMax 视频）</option>
    <option value="video_dashscope">video_dashscope（百炼 Wan 视频）</option>
  </select>
</div>;
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run --reporter=verbose src/features/admin/ModelServiceForm.test.tsx`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/admin/ModelServiceForm.tsx
git commit -m "feat(admin): 供应商表单增加协议下拉（video_minimax/video_dashscope）"
```

---

### Task 11: 前端 — UserModelServicesPage 拆分 video/image + 能力展示

**Files:**

- Modify: `frontend/src/features/admin/UserModelServicesPage.tsx`
- Test: `frontend/src/features/admin/UserModelServicesPage.test.tsx`

- [ ] **Step 1: 修改 `CAPABILITIES`**

```typescript
const CAPABILITIES = [
  {
    key: 'chat',
    label: '文本模型',
    description: '对话、文本生成、评估等',
    status: 'active' as const,
  },
  {
    key: 'embedding',
    label: '嵌入模型',
    description: '向量嵌入、语义检索',
    status: 'active' as const,
  },
  { key: 'rerank', label: '重排模型', description: '相关性重排、精排', status: 'active' as const },
  { key: 'video', label: '视频模型', description: '视频生成', status: 'active' as const },
  {
    key: 'image',
    label: '图片模型',
    description: '图片生成（即将支持）',
    status: 'coming_soon' as const,
  },
] as const;
```

- [ ] **Step 2: 在视频区块的已开通行下增加能力展示**

在 `ModelServiceSection` 中，对于 `capability === 'video'` 的行，在 api_host 行下方增加：

```tsx
{
  e.video_capabilities && (
    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>
      分辨率: {e.video_capabilities.resolutions.join(', ')} · 时长:{' '}
      {e.video_capabilities.duration.min}~{e.video_capabilities.duration.max}s · 比例:{' '}
      {e.video_capabilities.ratios.join(', ')}
    </div>
  );
}
```

- [ ] **Step 3: 验证**

Run: `cd frontend && npx vitest run --reporter=verbose src/features/admin/UserModelServicesPage.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/admin/UserModelServicesPage.tsx
git commit -m "feat(admin): 视频模型区块激活 + 能力展示，图片保持 coming_soon"
```

---

### Task 12: 前端 — VideoDisplayPage 动态渲染 + 403 处理

**Files:**

- Modify: `frontend/src/features/workflow/VideoDisplayPage.tsx`
- Test: `frontend/src/features/workflow/VideoDisplayPage.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VideoDisplayPage from './VideoDisplayPage';

const mockOptions = {
  data: {
    providerId: 'minimax',
    providerName: 'MiniMax',
    protocol: 'video_minimax',
    model: 'MiniMax-H3',
    capabilities: {
      resolutions: ['768P', '2K'],
      duration: { min: 4, max: 15 },
      ratios: ['16:9', '4:3', '1:1'],
    },
  },
};

vi.mock('../../api/video', () => ({
  videoApi: {
    getOptions: vi.fn(),
    listTasks: vi.fn().mockResolvedValue({ data: [] }),
    generate: vi.fn(),
  },
}));

describe('VideoDisplayPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows options from capabilities', async () => {
    const { videoApi } = await import('../../api/video');
    (videoApi.getOptions as any).mockResolvedValue(mockOptions);

    render(<VideoDisplayPage />);
    await waitFor(() => {
      // 分辨率下拉应包含 768P 和 2K
      expect(screen.getByText('768P')).toBeInTheDocument();
      expect(screen.getByText('2K')).toBeInTheDocument();
    });
  });

  it('shows 403 message when no video provider', async () => {
    const { videoApi } = await import('../../api/video');
    (videoApi.getOptions as any).mockRejectedValue(new Error('未开通视频生成服务，请联系管理员'));

    render(<VideoDisplayPage />);
    await waitFor(() => {
      expect(screen.getByText(/未开通视频生成服务/)).toBeInTheDocument();
    });
  });

  it('hides generate form when 403', async () => {
    const { videoApi } = await import('../../api/video');
    (videoApi.getOptions as any).mockRejectedValue(new Error('未开通视频生成服务，请联系管理员'));

    render(<VideoDisplayPage />);
    await waitFor(() => {
      // textarea 不应存在（表单隐藏）
      expect(screen.queryByPlaceholderText(/描述你想生成/)).not.toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run --reporter=verbose src/features/workflow/VideoDisplayPage.test.tsx`
Expected: FAIL

- [ ] **Step 3: 实现 VideoDisplayPage 重构**

```typescript
import { useCallback, useEffect, useRef, useState } from 'react';
import { videoApi, type VideoCapabilities, type VideoTask } from '../../api/video';

const POLL_INTERVAL_MS = 5000;
const NON_TERMINAL = new Set(['pending', 'queued', 'running']);

const STATUS_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  pending: { label: '生成中', bg: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' },
  queued: { label: '生成中', bg: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' },
  running: { label: '生成中', bg: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' },
  succeeded: { label: '已生成', bg: 'rgba(34,197,94,0.1)', color: 'var(--accent-green)' },
  failed: { label: '失败', bg: 'rgba(239,68,68,0.1)', color: '#ef4444' },
  expired: { label: '失败', bg: 'rgba(239,68,68,0.1)', color: '#ef4444' },
};

export default function VideoDisplayPage() {
  const [tasks, setTasks] = useState<VideoTask[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');

  // 动态选项（来自后端 capabilities）
  const [capabilities, setCapabilities] = useState<VideoCapabilities | null>(null);
  const [providerName, setProviderName] = useState('');
  const [optionsLoaded, setOptionsLoaded] = useState(false);
  const [noProvider, setNoProvider] = useState(false);

  const [resolution, setResolution] = useState('');
  const [duration, setDuration] = useState(5);
  const [ratio, setRatio] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 加载 options
  useEffect(() => {
    videoApi
      .getOptions()
      .then((res) => {
        const caps = res.data.capabilities;
        setCapabilities(caps);
        setProviderName(res.data.providerName);
        setResolution(caps.resolutions[0]);
        setRatio(caps.ratios[0]);
        setDuration(caps.duration.min);
        setOptionsLoaded(true);
        setNoProvider(false);
      })
      .catch(() => {
        setNoProvider(true);
        setOptionsLoaded(true);
      });
  }, []);

  const loadTasks = useCallback(async () => {
    try {
      const res = await videoApi.listTasks();
      setTasks(res.data);
    } catch { /* 静默 */ }
  }, []);

  useEffect(() => {
    videoApi.listTasks().then((res) => setTasks(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const hasActive = tasks.some((t) => NON_TERMINAL.has(t.status));
    if (hasActive && timerRef.current === null) {
      timerRef.current = setInterval(loadTasks, POLL_INTERVAL_MS);
    } else if (!hasActive && timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [tasks, loadTasks]);

  const selected = tasks.find((t) => t.id === selectedId) ?? null;

  const handleGenerate = async () => {
    setFormError('');
    if (!prompt.trim()) {
      setFormError('请输入视频描述');
      return;
    }
    setSubmitting(true);
    try {
      const res = await videoApi.generate({
        prompt: prompt.trim(),
        resolution,
        duration,
        ratio,
      });
      setSelectedId(res.data.taskId);
      setPrompt('');
      await loadTasks();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : '生成失败');
    } finally {
      setSubmitting(false);
    }
  };

  const durationOptions: number[] = capabilities
    ? Array.from(
        { length: capabilities.duration.max - capabilities.duration.min + 1 },
        (_, i) => capabilities.duration.min + i,
      )
    : [];

  if (!optionsLoaded) {
    return <div className="card" style={{ padding: 24 }}>加载中…</div>;
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      <div className="card-title">视频展示</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
        {noProvider
          ? '未开通视频生成服务，请联系管理员'
          : `使用 ${providerName} 生成方案演示视频`}
      </div>

      {noProvider ? null : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="描述你想生成的视频画面，例如：手机散热结构分层爆炸图动画"
            maxLength={7000}
            rows={3}
            style={{ width: '100%', resize: 'vertical', padding: 10, borderRadius: 8,
                     border: '1px solid var(--border)', background: 'var(--bg-card)',
                     color: 'var(--text-primary)', fontSize: 13, fontFamily: 'inherit' }}
          />
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', fontSize: 12 }}>
            <label style={{ color: 'var(--text-secondary)' }}>
              分辨率{' '}
              <select value={resolution} onChange={(e) => setResolution(e.target.value)}>
                {capabilities?.resolutions.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </label>
            <label style={{ color: 'var(--text-secondary)' }}>
              时长{' '}
              <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                {durationOptions.map((d) => (
                  <option key={d} value={d}>{d}s</option>
                ))}
              </select>
            </label>
            <label style={{ color: 'var(--text-secondary)' }}>
              宽高比{' '}
              <select value={ratio} onChange={(e) => setRatio(e.target.value)}>
                {capabilities?.ratios.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </label>
            <button
              onClick={handleGenerate}
              disabled={submitting}
              style={{ marginLeft: 'auto', padding: '8px 18px', borderRadius: 8,
                       border: 'none', background: '#f97316', color: '#fff',
                       fontSize: 13, fontWeight: 600,
                       cursor: submitting ? 'not-allowed' : 'pointer',
                       opacity: submitting ? 0.6 : 1 }}
            >
              {submitting ? '提交中…' : '生成视频'}
            </button>
          </div>
          {formError && <div style={{ fontSize: 12, color: '#ef4444' }}>{formError}</div>}
        </div>
      )}

      {/* 播放区和历史列表保持不变 */}
      <div style={{ borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)',
                    background: 'rgba(0,0,0,0.2)' }}>
        {!selected && (
          <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'var(--text-tertiary)', fontSize: 13 }}>
            选择下方任务以预览，或输入描述生成新视频
          </div>
        )}
        {selected && selected.status === 'succeeded' && selected.videoUrl && (
          <video key={selected.id} src={selected.videoUrl} controls
                 style={{ width: '100%', display: 'block', maxHeight: 420, background: '#000' }} />
        )}
        {selected && selected.status === 'succeeded' && !selected.videoUrl && (
          <div style={{ height: 280, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center', gap: 8,
                        color: 'var(--text-secondary)' }}>
            <i className="fa-solid fa-circle-exclamation" style={{ fontSize: 32, color: '#f97316' }} />
            <div style={{ fontSize: 13 }}>视频地址缺失</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              任务已成功但未返回视频地址，请重试或联系管理员
            </div>
          </div>
        )}
        {selected && NON_TERMINAL.has(selected.status) && (
          <div style={{ height: 280, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center', gap: 12,
                        color: 'var(--text-secondary)' }}>
            <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 32, color: '#f97316' }} />
            <div style={{ fontSize: 13 }}>视频生成中…</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              生成通常需要数十秒到数分钟
            </div>
          </div>
        )}
        {selected && (selected.status === 'failed' || selected.status === 'expired') && (
          <div style={{ height: 280, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center', gap: 8, color: '#ef4444' }}>
            <i className="fa-solid fa-circle-exclamation" style={{ fontSize: 32 }} />
            <div style={{ fontSize: 13 }}>生成失败</div>
            {selected.error && (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{selected.error}</div>
            )}
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                      marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
          <i className="fa-solid fa-film" style={{ color: '#f97316', fontSize: 12 }} />
          生成历史
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 4 }}>
            共 {tasks.length} 个
          </span>
        </div>
        {tasks.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', padding: '12px 0' }}>
            暂无生成记录
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {tasks.map((t) => {
            const badge = STATUS_BADGE[t.status] ?? STATUS_BADGE.pending;
            const active = t.id === selectedId;
            return (
              <div key={t.id} onClick={() => setSelectedId(t.id)}
                   style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
                            borderRadius: 8, background: active ? 'rgba(249,115,22,0.06)' : 'rgba(0,0,0,0.2)',
                            border: `1px solid ${active ? 'rgba(249,115,22,0.2)' : 'var(--border)'}`,
                            cursor: 'pointer' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)',
                                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.prompt}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {t.resolution} · {t.duration}s · {t.ratio} · {t.createdAt}
                  </div>
                </div>
                <span style={{ padding: '2px 8px', borderRadius: 4, background: badge.bg,
                               color: badge.color, fontSize: 10, flexShrink: 0 }}>
                  {badge.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run --reporter=verbose src/features/workflow/VideoDisplayPage.test.tsx`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/workflow/VideoDisplayPage.tsx
git commit -m "feat(video): VideoDisplayPage 动态渲染参数 + 403 处理，去品牌化"
```

---

### Task 13: 全量回归验证

- [ ] **Step 1: 后端全量回归**

Run: `cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -50`
Expected: 无失败（除已知不相关的测试外）

- [ ] **Step 2: 前端全量回归**

Run: `cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -50`
Expected: 无失败

- [ ] **Step 3: TypeScript 编译检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit final**

```bash
git add -A
git commit -m "chore: 视频多供应商重构全量回归验证"
```
