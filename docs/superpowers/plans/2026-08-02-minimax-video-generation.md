# MiniMax 视频生成集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 InnovOS 工作流第 7 阶段「方案视频化展示」从纯前端 Mock 替换为真正可用的 MiniMax-H3 文生视频能力（异步任务 + 后台轮询 + 持久化历史）。

**Architecture:** 后端新增 `video_tasks` 表、MiniMax REST 适配器（httpx 异步）、任务仓储服务、`/api/video` 路由、后台 asyncio 轮询器。前端新增 `api/video.ts` 客户端，用真实页面替换 `VideoDisplayMockPage`（删除 Mock 遗产）。MiniMax 是异步任务接口：创建返回 `task_id`，轮询 `GET /v2/query/video_generation/{task_id}`，成功时 `task.content.url` 即视频下载地址。

**Tech Stack:** FastAPI / psycopg2（`db_session`）/ httpx（async）/ pytest-asyncio（auto 模式）；React 19 / TypeScript / vitest / @testing-library/react。

## Global Constraints

- **DB 连接必须归还**：所有后端 DB 操作用 `with db_session() as db:`（CLAUDE.md 硬性要求）。
- **SQL 占位符**：用 `?`（框架自动转 `%s`）；动态列名需白名单。
- **时间戳**：表用 `TIMESTAMPTZ DEFAULT now()`；API 输出经 `app.utils.utc_iso()` 转 ISO。
- **归属字段**：资源归属用 `user["id"]`（`get_current_user` 返回 dict，仿 `api/tasks.py`）。
- **密钥来源**：`get_api_key_service().lease_key(provider_id="minimax").plaintext`；无密钥时报「未配置 MiniMax 密钥」。供应商行由管理员在 `/admin/model-providers` UI 录入，**不在代码里种子化**（main.py 既有约定）。
- **MiniMax 接口事实**：创建 `POST {host}/v2/video_generation` → `{"task_id": ...}`；查询 `GET {host}/v2/query/video_generation/{task_id}` → `{"task": {"status": ..., "content": {"url": ...}}}`；状态值 `queued/running/succeeded/failed/expired`；Bearer 鉴权。
- **参数白名单**：`duration ∈ [4,15]`、`resolution ∈ {768P,2K}`、`ratio ∈ {21:9,16:9,4:3,1:1,3:4,9:16}`、`prompt` 非空且 ≤7000 字符。
- **提交信息格式**：`<type>(<scope>): <description>`（feat/fix/refactor/test/chore）。
- **测试命令**：后端 `cd backend && uv run pytest tests/test_<f>.py -v`；前端 `cd frontend && npx vitest run <path>`。

---

## File Structure

**Backend（创建）**

- `backend/app/algorithm/clients/minimax_video.py` — MiniMax REST 适配器（async httpx）：`create_task` / `query_task`。纯网络层，不碰 DB。
- `backend/app/services/video_task_service.py` — `video_tasks` 仓储：create / set_remote_task / mark_failed / list_by_user / get / delete / list_active / apply_remote_status。API 与轮询器共用，避免 SQL 重复。
- `backend/app/api/video.py` — `/api/video` 路由：generate / tasks / tasks/{id} / DELETE。
- `backend/app/services/video_poller.py` — 后台 asyncio 轮询器（start/stop + 单轮 `poll_once`）。
- `backend/tests/test_minimax_video_adapter.py`
- `backend/tests/test_video_task_service.py`
- `backend/tests/test_video_api.py`
- `backend/tests/test_video_poller.py`

**Backend（修改）**

- `backend/app/tables/pg_schema.py` — 新增 `init_video_tasks(db)`，并在 `init_all_tables` 末尾调用。
- `backend/app/main.py` — 挂载 `video.router`；startup 启动轮询器、shutdown 停止。

**Frontend（创建）**

- `frontend/src/api/video.ts` — API 客户端（generate / listTasks / getTask / deleteTask）。
- `frontend/src/features/workflow/VideoDisplayPage.tsx` — 真实页面（表单 + 原生播放器 + 历史列表 + 轮询）。
- `frontend/src/api/__tests__/video.test.ts`
- `frontend/src/features/workflow/__tests__/VideoDisplayPage.test.tsx`

**Frontend（修改 / 删除）**

- `frontend/src/routes/index.tsx` — 路由 `workflow/video` 改指向 `VideoDisplayPage`。
- 删除 `frontend/src/features/workflow/VideoDisplayMockPage.tsx`
- 删除 `frontend/src/features/workflow/VideoDisplayView.tsx`（未被引用的孤儿）

---

## Task 1: video_tasks 数据表

**Files:**

- Modify: `backend/app/tables/pg_schema.py`（新增 `init_video_tasks`，在 `init_all_tables` 内调用）
- Test: `backend/tests/test_video_schema.py`

**Interfaces:**

- Produces: `init_video_tasks(db)` — 幂等建表（`CREATE TABLE IF NOT EXISTS`）+ 两个索引。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_video_schema.py`:

```python
"""video_tasks 表 DDL 测试 — 验证 init_video_tasks 发出预期 SQL。"""
from unittest.mock import MagicMock

from app.tables.pg_schema import init_video_tasks


def test_init_video_tasks_creates_table_and_indexes():
    db = MagicMock()
    init_video_tasks(db)

    sqls = [call.args[0] for call in db.execute.call_args_list]
    joined = "\n".join(sqls)

    assert "CREATE TABLE IF NOT EXISTS video_tasks" in joined
    assert "remote_task_id" in joined
    assert "video_url" in joined
    # 两个索引
    assert "idx_video_tasks_user" in joined
    assert "idx_video_tasks_status" in joined
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_video_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'init_video_tasks'`

- [ ] **Step 3: 实现 init_video_tasks**

在 `backend/app/tables/pg_schema.py` 的 per-table DDL 区（例如 `init_feedbacks` 附近）新增：

```python
def init_video_tasks(db):
    """视频生成任务表 — MiniMax 文生视频异步任务持久化。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS video_tasks (
            id              TEXT PRIMARY KEY,
            user_id         INTEGER NOT NULL,
            provider_id     TEXT NOT NULL DEFAULT 'minimax',
            model           TEXT NOT NULL DEFAULT 'MiniMax-H3',
            prompt          TEXT NOT NULL,
            resolution      TEXT NOT NULL DEFAULT '768P',
            duration        INTEGER NOT NULL DEFAULT 5,
            ratio           TEXT NOT NULL DEFAULT '16:9',
            remote_task_id  TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            video_url       TEXT,
            error           TEXT,
            created_at      TIMESTAMPTZ DEFAULT now(),
            updated_at      TIMESTAMPTZ DEFAULT now()
        );
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_video_tasks_user "
        "ON video_tasks(user_id, created_at DESC)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_video_tasks_status "
        "ON video_tasks(status)"
    )
```

然后在 `init_all_tables(db)` 函数体末尾（`init_problem_modelings(db)` 之后）追加一行：

```python
    init_video_tasks(db)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_video_schema.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/tables/pg_schema.py backend/tests/test_video_schema.py
git commit -m "feat(db): add video_tasks table for MiniMax video generation"
```

---

## Task 2: MiniMax 适配器

**Files:**

- Create: `backend/app/algorithm/clients/minimax_video.py`
- Test: `backend/tests/test_minimax_video_adapter.py`

**Interfaces:**

- Consumes: 无（纯网络层）。
- Produces:
  - `class MinimaxVideoError(Exception)` — 携带 MiniMax 错误 message。
  - `class MinimaxVideoAdapter`：
    - `async create_task(self, *, api_key, api_host, prompt, resolution, duration, ratio) -> str`（返回 remote task_id）
    - `async query_task(self, *, api_key, api_host, remote_task_id) -> dict`（返回 `{"status": str, "video_url": str|None, "error": str|None}`）
  - 模块级单例 `minimax_video_adapter = MinimaxVideoAdapter()`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_minimax_video_adapter.py`:

```python
"""MiniMax 视频适配器测试 — mock httpx.AsyncClient。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.algorithm.clients.minimax_video import (
    MinimaxVideoAdapter,
    MinimaxVideoError,
)


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def adapter():
    return MinimaxVideoAdapter()


async def test_create_task_posts_and_returns_task_id(adapter):
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
            prompt="一个男孩在海边打篮球",
            resolution="2K",
            duration=5,
            ratio="16:9",
        )

    assert task_id == "424010985738629"
    # 验证请求 URL 与 body
    call = mock_client.post.call_args
    assert call.args[0] == "https://api.minimaxi.com/v2/video_generation"
    body = call.kwargs["json"]
    assert body["model"] == "MiniMax-H3"
    assert body["content"] == [{"type": "text", "text": "一个男孩在海边打篮球"}]
    assert body["resolution"] == "2K"
    assert body["duration"] == 5
    assert body["ratio"] == "16:9"
    # Bearer 鉴权
    assert call.kwargs["headers"]["Authorization"] == "Bearer sk-test"


async def test_create_task_raises_on_error(adapter):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(
            422,
            {
                "type": "error",
                "error": {
                    "type": "unprocessable_entity_error",
                    "message": "video description contains sensitive content (1026)",
                },
            },
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(MinimaxVideoError) as exc:
            await adapter.create_task(
                api_key="sk-test",
                api_host="https://api.minimaxi.com",
                prompt="x",
                resolution="2K",
                duration=5,
                ratio="16:9",
            )
    assert "sensitive content" in str(exc.value)


async def test_query_task_succeeded_returns_url(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            200,
            {
                "task": {
                    "id": "424010985738629",
                    "status": "succeeded",
                    "content": {"url": "https://cdn.example.com/out.mp4"},
                }
            },
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test",
            api_host="https://api.minimaxi.com",
            remote_task_id="424010985738629",
        )

    assert result["status"] == "succeeded"
    assert result["video_url"] == "https://cdn.example.com/out.mp4"
    assert result["error"] is None
    # 验证 GET URL
    assert (
        mock_client.get.call_args.args[0]
        == "https://api.minimaxi.com/v2/query/video_generation/424010985738629"
    )


async def test_query_task_running_has_no_url(adapter):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(
        return_value=_mock_response(200, {"task": {"id": "x", "status": "running"}})
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.algorithm.clients.minimax_video.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await adapter.query_task(
            api_key="sk-test",
            api_host="https://api.minimaxi.com",
            remote_task_id="x",
        )

    assert result["status"] == "running"
    assert result["video_url"] is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_minimax_video_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.algorithm.clients.minimax_video'`

- [ ] **Step 3: 实现适配器**

Create `backend/app/algorithm/clients/minimax_video.py`:

```python
"""MiniMax 视频生成 V2 适配器（Hailuo-03 / MiniMax-H3）。

MiniMax 非 OpenAI 兼容协议，用 httpx 直打 REST。异步任务模型：
- create_task: POST /v2/video_generation → {"task_id": ...}
- query_task:  GET  /v2/query/video_generation/{task_id}
               → {"task": {"status": ..., "content": {"url": ...}}}
  成功时 task.content.url 即视频下载地址（H3 无需 file_id 换取）。

实例不持有 api_key，每次调用传入。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "MiniMax-H3"


class MinimaxVideoError(Exception):
    """MiniMax 接口返回非 2xx，携带其 error message。"""


class MinimaxVideoAdapter:
    """MiniMax 视频生成 REST 适配器（即用即构造 client）。"""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    @staticmethod
    def _extract_error_message(data: Any, status_code: int) -> str:
        """从 OpenAI 风格错误体提取 message。"""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
        return f"MiniMax API error (HTTP {status_code})"

    async def create_task(
        self,
        *,
        api_key: str,
        api_host: str,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
    ) -> str:
        """创建文生视频任务，返回 MiniMax 侧 task_id。"""
        url = f"{api_host.rstrip('/')}/v2/video_generation"
        body = {
            "model": DEFAULT_MODEL,
            "content": [{"type": "text", "text": prompt}],
            "resolution": resolution,
            "duration": duration,
            "ratio": ratio,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
        if resp.status_code >= 400:
            raise MinimaxVideoError(
                self._extract_error_message(resp.json(), resp.status_code)
            )
        task_id = resp.json().get("task_id")
        if not task_id:
            raise MinimaxVideoError("MiniMax 未返回 task_id")
        return str(task_id)

    async def query_task(
        self,
        *,
        api_key: str,
        api_host: str,
        remote_task_id: str,
    ) -> dict:
        """查询任务状态。返回 {status, video_url, error}。"""
        url = f"{api_host.rstrip('/')}/v2/query/video_generation/{remote_task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            raise MinimaxVideoError(
                self._extract_error_message(resp.json(), resp.status_code)
            )
        task = resp.json().get("task", {})
        status = task.get("status", "")
        video_url = None
        if status == "succeeded":
            video_url = (task.get("content") or {}).get("url")
        error = task.get("error") if status in ("failed", "expired") else None
        return {"status": status, "video_url": video_url, "error": error}


minimax_video_adapter = MinimaxVideoAdapter()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_minimax_video_adapter.py -v`
Expected: PASS（4 个测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/algorithm/clients/minimax_video.py backend/tests/test_minimax_video_adapter.py
git commit -m "feat(video): add MiniMax video generation REST adapter"
```

---

## Task 3: 视频任务仓储服务

**Files:**

- Create: `backend/app/services/video_task_service.py`
- Test: `backend/tests/test_video_task_service.py`

**Interfaces:**

- Consumes: `db_session`（`app.database`）、`utc_iso`（`app.utils`）。
- Produces: `class VideoTaskService`（模块单例 `video_task_service`）：
  - `create(user_id, *, prompt, resolution, duration, ratio) -> dict`（status='pending'，生成 uuid id）
  - `set_remote_task(task_id, remote_task_id) -> None`（status='queued'）
  - `mark_failed(task_id, error) -> None`（status='failed'）
  - `get(task_id) -> dict | None`
  - `list_by_user(user_id) -> list[dict]`（created_at DESC）
  - `delete(task_id, user_id) -> bool`
  - `list_active() -> list[dict]`（status IN pending/queued/running，供轮询器）
  - `apply_remote_status(task_id, *, status, video_url, error) -> None`（轮询器回写）
  - 返回 dict 为 camelCase：`id, userId, prompt, resolution, duration, ratio, remoteTaskId, status, videoUrl, error, createdAt, updatedAt`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_video_task_service.py`:

```python
"""视频任务仓储服务测试 — 用可控 fake db_session。"""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.services import video_task_service as vts_mod
from app.services.video_task_service import VideoTaskService


class FakeCursor:
    def __init__(self, fetchone_val=None, fetchall_val=None):
        self._fetchone = fetchone_val
        self._fetchall = fetchall_val or []

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall


@pytest.fixture
def fake_db(monkeypatch):
    """patch 服务模块内的 db_session，返回 (db_mock, 捕获的 SQL 列表)。"""
    db = MagicMock()
    captured: list[tuple[str, object]] = []

    def _execute(sql, params=None):
        captured.append((sql, params))
        return db._cursor if hasattr(db, "_cursor") else FakeCursor()

    db.execute = _execute
    db._cursor = FakeCursor()

    @contextmanager
    def _session():
        yield db

    monkeypatch.setattr(vts_mod, "db_session", _session)
    return db, captured


def test_create_inserts_pending_task_and_returns_dict(fake_db):
    db, captured = fake_db
    # INSERT ... RETURNING id 后服务会 SELECT 回读；给 SELECT 一个行
    row = {
        "id": "abc", "user_id": 1, "provider_id": "minimax", "model": "MiniMax-H3",
        "prompt": "p", "resolution": "768P", "duration": 5, "ratio": "16:9",
        "remote_task_id": None, "status": "pending", "video_url": None,
        "error": None, "created_at": "2026-08-02 10:00:00", "updated_at": "2026-08-02 10:00:00",
    }
    db._cursor = FakeCursor(fetchone_val=row)

    svc = VideoTaskService()
    result = svc.create(1, prompt="p", resolution="768P", duration=5, ratio="16:9")

    assert result["status"] == "pending"
    assert result["userId"] == 1
    # 第一条 SQL 是 INSERT
    insert_sql, insert_params = captured[0]
    assert "INSERT INTO video_tasks" in insert_sql
    assert "p" in insert_params  # prompt 在参数里


def test_list_by_user_filters_by_user(fake_db):
    db, captured = fake_db
    db._cursor = FakeCursor(fetchall_val=[])

    svc = VideoTaskService()
    svc.list_by_user(7)

    sql, params = captured[0]
    assert "FROM video_tasks" in sql
    assert "user_id" in sql
    assert 7 in params


def test_list_active_selects_nonterminal_statuses(fake_db):
    db, captured = fake_db
    db._cursor = FakeCursor(fetchall_val=[])

    svc = VideoTaskService()
    svc.list_active()

    sql, _ = captured[0]
    assert "status" in sql
    for s in ("pending", "queued", "running"):
        assert s in sql


def test_apply_remote_status_updates_url(fake_db):
    db, captured = fake_db
    svc = VideoTaskService()
    svc.apply_remote_status(
        "abc", status="succeeded", video_url="https://x/y.mp4", error=None
    )

    sql, params = captured[0]
    assert "UPDATE video_tasks" in sql
    assert "succeeded" in params
    assert "https://x/y.mp4" in params
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_video_task_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.video_task_service'`

- [ ] **Step 3: 实现服务**

Create `backend/app/services/video_task_service.py`:

```python
"""视频生成任务仓储 — video_tasks 表的唯一 SQL 入口。

API 层与后台轮询器共用本服务，避免 SQL 重复。所有 DB 操作走 db_session。
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.database import db_session
from app.utils import utc_iso

ACTIVE_STATUSES = ("pending", "queued", "running")


def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row) if not isinstance(row, dict) else row
    return {
        "id": d.get("id"),
        "userId": d.get("user_id"),
        "providerId": d.get("provider_id"),
        "model": d.get("model"),
        "prompt": d.get("prompt"),
        "resolution": d.get("resolution"),
        "duration": d.get("duration"),
        "ratio": d.get("ratio"),
        "remoteTaskId": d.get("remote_task_id"),
        "status": d.get("status"),
        "videoUrl": d.get("video_url"),
        "error": d.get("error"),
        "createdAt": utc_iso(d.get("created_at")),
        "updatedAt": utc_iso(d.get("updated_at")),
    }


class VideoTaskService:
    def create(
        self,
        user_id: int,
        *,
        prompt: str,
        resolution: str,
        duration: int,
        ratio: str,
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        with db_session() as db:
            db.execute(
                "INSERT INTO video_tasks "
                "(id, user_id, prompt, resolution, duration, ratio, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                (task_id, user_id, prompt, resolution, duration, ratio),
            )
            row = db.execute(
                "SELECT * FROM video_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _row_to_dict(row)

    def set_remote_task(self, task_id: str, remote_task_id: str) -> None:
        with db_session() as db:
            db.execute(
                "UPDATE video_tasks SET remote_task_id = ?, status = 'queued', "
                "updated_at = now() WHERE id = ?",
                (remote_task_id, task_id),
            )

    def mark_failed(self, task_id: str, error: str) -> None:
        with db_session() as db:
            db.execute(
                "UPDATE video_tasks SET status = 'failed', error = ?, "
                "updated_at = now() WHERE id = ?",
                (error, task_id),
            )

    def get(self, task_id: str) -> Optional[dict[str, Any]]:
        with db_session() as db:
            row = db.execute(
                "SELECT * FROM video_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_by_user(self, user_id: int) -> list[dict[str, Any]]:
        with db_session() as db:
            rows = db.execute(
                "SELECT * FROM video_tasks WHERE user_id = ? "
                "ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def delete(self, task_id: str, user_id: int) -> bool:
        with db_session() as db:
            cur = db.execute(
                "DELETE FROM video_tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
            return (cur.rowcount or 0) > 0

    def list_active(self) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        with db_session() as db:
            rows = db.execute(
                f"SELECT * FROM video_tasks WHERE status IN ({placeholders})",
                ACTIVE_STATUSES,
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def apply_remote_status(
        self,
        task_id: str,
        *,
        status: str,
        video_url: Optional[str],
        error: Optional[str],
    ) -> None:
        with db_session() as db:
            db.execute(
                "UPDATE video_tasks SET status = ?, video_url = ?, error = ?, "
                "updated_at = now() WHERE id = ?",
                (status, video_url, error, task_id),
            )


video_task_service = VideoTaskService()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_video_task_service.py -v`
Expected: PASS（4 个测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/video_task_service.py backend/tests/test_video_task_service.py
git commit -m "feat(video): add video task repository service"
```

---

## Task 4: /api/video 路由

**Files:**

- Create: `backend/app/api/video.py`
- Test: `backend/tests/test_video_api.py`

**Interfaces:**

- Consumes: `video_task_service`（Task 3）、`minimax_video_adapter` + `MinimaxVideoError`（Task 2）、`get_api_key_service`（`app.services.api_key_service`）、`get_current_user`（`app.auth`）。
- Produces: `router`（prefix `/api/video`），端点：
  - `POST /api/video/generate` → `{data: {taskId}, message, code}`
  - `GET /api/video/tasks` → `{data: [...], message, code}`
  - `GET /api/video/tasks/{id}` → `{data: {...}, message, code}`（非本人 404）
  - `DELETE /api/video/tasks/{id}` → `{message, code}`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_video_api.py`:

```python
"""/api/video 路由测试 — TestClient + 依赖覆盖 + mock 服务/适配器。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import video as video_api
from app.auth import get_current_user


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(video_api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "test"}
    with TestClient(app) as c:
        yield c


def test_generate_creates_task_and_returns_id(client):
    created = {"id": "task-1", "status": "pending"}
    with patch.object(
        video_api.video_task_service, "create", return_value=created
    ) as mock_create, patch.object(
        video_api.video_task_service, "set_remote_task"
    ) as mock_set, patch.object(
        video_api, "_lease_minimax_key", return_value=("sk-test", "https://api.minimaxi.com")
    ), patch.object(
        video_api.minimax_video_adapter,
        "create_task",
        new=AsyncMock(return_value="remote-123"),
    ):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "一只猫", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["taskId"] == "task-1"
    mock_create.assert_called_once()
    mock_set.assert_called_once_with("task-1", "remote-123")


def test_generate_rejects_invalid_duration(client):
    resp = client.post(
        "/api/video/generate",
        json={"prompt": "x", "resolution": "768P", "duration": 99, "ratio": "16:9"},
    )
    assert resp.status_code == 422


def test_generate_rejects_invalid_ratio(client):
    resp = client.post(
        "/api/video/generate",
        json={"prompt": "x", "resolution": "768P", "duration": 5, "ratio": "adaptive"},
    )
    assert resp.status_code == 422


def test_generate_rejects_empty_prompt(client):
    resp = client.post(
        "/api/video/generate",
        json={"prompt": "   ", "resolution": "768P", "duration": 5, "ratio": "16:9"},
    )
    assert resp.status_code == 422


def test_generate_no_key_returns_error(client):
    with patch.object(video_api, "_lease_minimax_key", return_value=(None, None)):
        resp = client.post(
            "/api/video/generate",
            json={"prompt": "x", "resolution": "768P", "duration": 5, "ratio": "16:9"},
        )
    assert resp.status_code == 400
    assert "MiniMax" in resp.json()["detail"]


def test_list_tasks_returns_user_tasks(client):
    with patch.object(
        video_api.video_task_service,
        "list_by_user",
        return_value=[{"id": "t1", "status": "succeeded"}],
    ):
        resp = client.get("/api/video/tasks")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["id"] == "t1"


def test_get_task_foreign_returns_404(client):
    # 任务存在但 user_id 不匹配
    with patch.object(
        video_api.video_task_service, "get", return_value={"id": "t1", "userId": 999}
    ):
        resp = client.get("/api/video/tasks/t1")
    assert resp.status_code == 404


def test_delete_task(client):
    with patch.object(video_api.video_task_service, "delete", return_value=True):
        resp = client.delete("/api/video/tasks/t1")
    assert resp.status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_video_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.video'`

- [ ] **Step 3: 实现路由**

Create `backend/app/api/video.py`:

```python
"""视频生成 API — MiniMax 文生视频（异步任务）。

POST /api/video/generate   创建任务（立即返回 taskId，后台轮询推进）
GET  /api/video/tasks      当前用户任务列表
GET  /api/video/tasks/{id} 单任务详情
DELETE /api/video/tasks/{id} 删除本地任务记录
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.algorithm.clients.minimax_video import (
    MinimaxVideoError,
    minimax_video_adapter,
)
from app.auth import get_current_user
from app.services.api_key_service import get_api_key_service
from app.services.video_task_service import video_task_service

router = APIRouter(prefix="/api/video", tags=["video"])

MINIMAX_PROVIDER_ID = "minimax"

ALLOWED_RESOLUTIONS = {"768P", "2K"}
ALLOWED_RATIOS = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}


class GenerateInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=7000)
    resolution: str = "768P"
    duration: int = Field(default=5, ge=4, le=15)
    ratio: str = "16:9"


def _lease_minimax_key() -> tuple[str | None, str | None]:
    """租用 minimax 密钥并读取 api_host。返回 (plaintext, api_host)。"""
    from app.database import db_session

    svc = get_api_key_service()
    lease = svc.lease_key(provider_id=MINIMAX_PROVIDER_ID)
    if not lease:
        return None, None
    with db_session() as db:
        row = db.execute(
            "SELECT api_host FROM model_providers WHERE provider_id = ?",
            (MINIMAX_PROVIDER_ID,),
        ).fetchone()
    api_host = row["api_host"] if row else "https://api.minimaxi.com"
    return lease.plaintext, api_host


@router.post("/generate")
async def generate(body: GenerateInput, user: dict = Depends(get_current_user)):
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="prompt 不能为空")
    if body.resolution not in ALLOWED_RESOLUTIONS:
        raise HTTPException(status_code=422, detail=f"非法分辨率: {body.resolution}")
    if body.ratio not in ALLOWED_RATIOS:
        raise HTTPException(status_code=422, detail=f"非法宽高比: {body.ratio}")

    task = video_task_service.create(
        user["id"],
        prompt=body.prompt.strip(),
        resolution=body.resolution,
        duration=body.duration,
        ratio=body.ratio,
    )

    api_key, api_host = _lease_minimax_key()
    if not api_key:
        video_task_service.mark_failed(task["id"], "未配置 MiniMax 密钥")
        raise HTTPException(status_code=400, detail="未配置 MiniMax 密钥")

    try:
        remote_task_id = await minimax_video_adapter.create_task(
            api_key=api_key,
            api_host=api_host,
            prompt=body.prompt.strip(),
            resolution=body.resolution,
            duration=body.duration,
            ratio=body.ratio,
        )
    except MinimaxVideoError as exc:
        video_task_service.mark_failed(task["id"], str(exc))
        raise HTTPException(status_code=400, detail=str(exc))

    video_task_service.set_remote_task(task["id"], remote_task_id)
    return {"data": {"taskId": task["id"]}, "message": "success", "code": 200}


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

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_video_api.py -v`
Expected: PASS（8 个测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/video.py backend/tests/test_video_api.py
git commit -m "feat(video): add /api/video routes for generation and history"
```

---

## Task 5: 后台轮询器

**Files:**

- Create: `backend/app/services/video_poller.py`
- Test: `backend/tests/test_video_poller.py`

**Interfaces:**

- Consumes: `video_task_service`（Task 3）、`minimax_video_adapter`（Task 2）、`get_api_key_service`。
- Produces: `class VideoPoller`（模块单例 `video_poller`）：
  - `async start() -> None`（启动 asyncio 循环）
  - `async stop() -> None`（置停止事件）
  - `async poll_once() -> int`（执行一轮，返回推进到终态的任务数；可独立测试）

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_video_poller.py`:

```python
"""后台视频轮询器测试 — mock 服务 + 适配器，验证单轮状态推进。"""
from unittest.mock import AsyncMock, patch

from app.services import video_poller as vp_mod
from app.services.video_poller import VideoPoller


def test_poll_once_advances_succeeded_task():
    poller = VideoPoller(interval_seconds=5)
    active = [
        {"id": "t1", "remoteTaskId": "r1"},
        {"id": "t2", "remoteTaskId": "r2"},
    ]
    query_results = {
        "r1": {"status": "succeeded", "video_url": "https://x/1.mp4", "error": None},
        "r2": {"status": "running", "video_url": None, "error": None},
    }

    with patch.object(
        vp_mod.video_task_service, "list_active", return_value=active
    ), patch.object(
        vp_mod, "_lease_minimax_key", return_value=("sk", "https://api.minimaxi.com")
    ), patch.object(
        vp_mod.minimax_video_adapter,
        "query_task",
        new=AsyncMock(side_effect=lambda *, api_key, api_host, remote_task_id: query_results[remote_task_id]),
    ), patch.object(
        vp_mod.video_task_service, "apply_remote_status"
    ) as mock_apply:
        advanced = _run(poller.poll_once())

    # 只有 succeeded 的 t1 被回写终态；running 的 t2 也回写（状态同步）
    applied_ids = {c.args[0] for c in mock_apply.call_args_list}
    assert "t1" in applied_ids
    assert "t2" in applied_ids


def test_poll_once_no_key_skips():
    poller = VideoPoller(interval_seconds=5)
    with patch.object(
        vp_mod.video_task_service,
        "list_active",
        return_value=[{"id": "t1", "remoteTaskId": "r1"}],
    ), patch.object(vp_mod, "_lease_minimax_key", return_value=(None, None)), patch.object(
        vp_mod.video_task_service, "apply_remote_status"
    ) as mock_apply:
        _run(poller.poll_once())
    mock_apply.assert_not_called()


def test_poll_once_query_error_does_not_crash():
    poller = VideoPoller(interval_seconds=5)
    with patch.object(
        vp_mod.video_task_service,
        "list_active",
        return_value=[{"id": "t1", "remoteTaskId": "r1"}],
    ), patch.object(
        vp_mod, "_lease_minimax_key", return_value=("sk", "https://api.minimaxi.com")
    ), patch.object(
        vp_mod.minimax_video_adapter,
        "query_task",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ), patch.object(vp_mod.video_task_service, "apply_remote_status") as mock_apply:
        # 不应抛出
        _run(poller.poll_once())
    mock_apply.assert_not_called()


def _run(coro):
    import asyncio

    return asyncio.get_event_loop().run_until_complete(coro)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_video_poller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.video_poller'`

- [ ] **Step 3: 实现轮询器**

Create `backend/app/services/video_poller.py`:

```python
"""后台视频任务轮询器。

startup 启动 asyncio 循环，每 interval_seconds 秒扫描未终态任务，
向 MiniMax 查询并回写状态。用户离开页面任务仍推进。
"""
from __future__ import annotations

import asyncio
import logging

from app.algorithm.clients.minimax_video import (
    MinimaxVideoError,
    minimax_video_adapter,
)
from app.services.video_task_service import video_task_service

logger = logging.getLogger(__name__)

MINIMAX_PROVIDER_ID = "minimax"
TERMINAL_STATUSES = {"succeeded", "failed", "expired"}


def _lease_minimax_key() -> tuple[str | None, str | None]:
    from app.database import db_session
    from app.services.api_key_service import get_api_key_service

    svc = get_api_key_service()
    lease = svc.lease_key(provider_id=MINIMAX_PROVIDER_ID)
    if not lease:
        return None, None
    with db_session() as db:
        row = db.execute(
            "SELECT api_host FROM model_providers WHERE provider_id = ?",
            (MINIMAX_PROVIDER_ID,),
        ).fetchone()
    api_host = row["api_host"] if row else "https://api.minimaxi.com"
    return lease.plaintext, api_host


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
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"视频轮询轮次异常: {exc}")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    async def poll_once(self) -> int:
        """执行一轮轮询，返回回写的任务数。"""
        active = video_task_service.list_active()
        if not active:
            return 0

        api_key, api_host = _lease_minimax_key()
        if not api_key:
            logger.debug("无 MiniMax 密钥，跳过本轮轮询")
            return 0

        count = 0
        for task in active:
            remote_id = task.get("remoteTaskId")
            if not remote_id:
                continue
            try:
                result = await minimax_video_adapter.query_task(
                    api_key=api_key, api_host=api_host, remote_task_id=remote_id
                )
            except (MinimaxVideoError, Exception) as exc:  # noqa: BLE001
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

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_video_poller.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/video_poller.py backend/tests/test_video_poller.py
git commit -m "feat(video): add background poller to advance MiniMax tasks"
```

---

## Task 6: 接入 main.py

**Files:**

- Modify: `backend/app/main.py`（挂载路由 + startup/shutdown 接线）

**Interfaces:**

- Consumes: `app.api.video.router`（Task 4）、`app.services.video_poller.video_poller`（Task 5）。

- [ ] **Step 1: 挂载路由**

在 `backend/app/main.py` 顶部 import 区（`from app.api import ... models as models_api` 附近）加入：

```python
from app.api import video as video_api
```

在路由挂载区（`app_.include_router(models_api.router)` 附近）加入：

```python
app_.include_router(video_api.router)
```

- [ ] **Step 2: startup 启动轮询器**

在 `startup()` 函数内，知识库作业系统启动之后（`await knowledge_orchestration_service.start()` 那段之后）加入：

```python
    # 4.6 启动视频生成轮询器
    from app.services.video_poller import video_poller

    await video_poller.start()
    logger.info("视频生成轮询器已启动")
```

- [ ] **Step 3: shutdown 停止轮询器**

在 `shutdown()` 函数内，`await backup_service.stop()` 之后加入：

```python
    # 停止视频生成轮询器
    from app.services.video_poller import video_poller

    await video_poller.stop()
```

- [ ] **Step 4: 验证应用可导入**

Run: `cd backend && uv run python -c "import app.main; print('ok')"`
Expected: 输出 `ok`（无 ImportError / SyntaxError）

- [ ] **Step 5: 跑全量后端测试确认无回归**

Run: `cd backend && uv run pytest -q`
Expected: 全部通过（含新增 4 个测试文件）

- [ ] **Step 6: 提交**

```bash
git add backend/app/main.py
git commit -m "feat(video): wire video router and poller into app lifecycle"
```

---

## Task 7: 前端 API 客户端

**Files:**

- Create: `frontend/src/api/video.ts`
- Test: `frontend/src/api/__tests__/video.test.ts`

**Interfaces:**

- Consumes: `apiRequest`（`./client`）。
- Produces:
  - `interface VideoTask`（camelCase，对齐后端 `_row_to_dict`）：`id, userId, prompt, resolution, duration, ratio, remoteTaskId, status, videoUrl, error, createdAt, updatedAt`
  - `videoApi.generate(input)` / `videoApi.listTasks()` / `videoApi.getTask(id)` / `videoApi.deleteTask(id)`

- [ ] **Step 1: 写失败测试**

Create `frontend/src/api/__tests__/video.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('videoApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('generate posts prompt + params to /api/video/generate', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ data: { taskId: 't1' }, code: 200 })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { videoApi } = await import('../video');
    const res = await videoApi.generate({
      prompt: '一只猫',
      resolution: '768P',
      duration: 5,
      ratio: '16:9',
    });

    expect(res.data.taskId).toBe('t1');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/video/generate'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          prompt: '一只猫',
          resolution: '768P',
          duration: 5,
          ratio: '16:9',
        }),
      }),
    );
  });

  it('listTasks calls GET /api/video/tasks', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () =>
        Promise.resolve(JSON.stringify({ data: [{ id: 't1', status: 'succeeded' }], code: 200 })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { videoApi } = await import('../video');
    const res = await videoApi.listTasks();

    expect(res.data[0].id).toBe('t1');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/video/tasks'),
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('deleteTask calls DELETE /api/video/tasks/{id}', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ code: 200 })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { videoApi } = await import('../video');
    await videoApi.deleteTask('t1');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/video/tasks/t1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/api/__tests__/video.test.ts`
Expected: FAIL — 无法解析 `../video`

- [ ] **Step 3: 实现客户端**

Create `frontend/src/api/video.ts`:

```typescript
// 视频生成 API 客户端（MiniMax 文生视频，异步任务）。
//
// 端点契约（见 backend/app/api/video.py）：
// - POST   /api/video/generate      {prompt, resolution, duration, ratio} → {data:{taskId}}
// - GET    /api/video/tasks         → {data: VideoTask[]}
// - GET    /api/video/tasks/{id}    → {data: VideoTask}
// - DELETE /api/video/tasks/{id}    → {code}
import { apiRequest } from './client';

export type VideoStatus = 'pending' | 'queued' | 'running' | 'succeeded' | 'failed' | 'expired';

export interface VideoTask {
  id: string;
  userId: number;
  providerId: string;
  model: string;
  prompt: string;
  resolution: string;
  duration: number;
  ratio: string;
  remoteTaskId: string | null;
  status: VideoStatus;
  videoUrl: string | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GenerateInput {
  prompt: string;
  resolution: '768P' | '2K';
  duration: number;
  ratio: '21:9' | '16:9' | '4:3' | '1:1' | '3:4' | '9:16';
}

interface Envelope<T> {
  data: T;
  message?: string;
  code: number;
}

export const videoApi = {
  generate(input: GenerateInput): Promise<Envelope<{ taskId: string }>> {
    return apiRequest('/api/video/generate', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  listTasks(): Promise<Envelope<VideoTask[]>> {
    return apiRequest('/api/video/tasks');
  },

  getTask(id: string): Promise<Envelope<VideoTask>> {
    return apiRequest(`/api/video/tasks/${id}`);
  },

  deleteTask(id: string): Promise<Envelope<unknown>> {
    return apiRequest(`/api/video/tasks/${id}`, { method: 'DELETE' });
  },
};
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/api/__tests__/video.test.ts`
Expected: PASS（3 个测试）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/video.ts frontend/src/api/__tests__/video.test.ts
git commit -m "feat(video): add frontend video API client"
```

---

## Task 8: 前端页面替换 Mock

**Files:**

- Create: `frontend/src/features/workflow/VideoDisplayPage.tsx`
- Modify: `frontend/src/routes/index.tsx`（改路由指向）
- Delete: `frontend/src/features/workflow/VideoDisplayMockPage.tsx`
- Delete: `frontend/src/features/workflow/VideoDisplayView.tsx`
- Test: `frontend/src/features/workflow/__tests__/VideoDisplayPage.test.tsx`

**Interfaces:**

- Consumes: `videoApi` + `VideoTask`（Task 7）。
- Produces: 默认导出 `VideoDisplayPage`（表单 + 原生播放器 + 历史列表 + 5s 轮询至无未终态任务）。

- [ ] **Step 1: 写失败测试**

Create `frontend/src/features/workflow/__tests__/VideoDisplayPage.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// mock 掉 api 层
vi.mock('../../../api/video', () => ({
  videoApi: {
    generate: vi.fn(),
    listTasks: vi.fn(),
    getTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}));

import { videoApi } from '../../../api/video';
import VideoDisplayPage from '../VideoDisplayPage';

const mockGenerate = videoApi.generate as ReturnType<typeof vi.fn>;
const mockListTasks = videoApi.listTasks as ReturnType<typeof vi.fn>;

describe('VideoDisplayPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListTasks.mockResolvedValue({ data: [], code: 200 });
  });

  it('renders prompt form and submits generate', async () => {
    mockGenerate.mockResolvedValue({ data: { taskId: 't1' }, code: 200 });
    render(<VideoDisplayPage />);

    const textarea = screen.getByPlaceholderText(/描述/i);
    fireEvent.change(textarea, { target: { value: '一只猫在跳舞' } });
    fireEvent.click(screen.getByRole('button', { name: /生成视频/ }));

    await waitFor(() =>
      expect(mockGenerate).toHaveBeenCalledWith(
        expect.objectContaining({ prompt: '一只猫在跳舞' }),
      ),
    );
  });

  it('renders history list with status badges', async () => {
    mockListTasks.mockResolvedValue({
      data: [
        {
          id: 't1',
          userId: 1,
          providerId: 'minimax',
          model: 'MiniMax-H3',
          prompt: '已完成的视频',
          resolution: '768P',
          duration: 5,
          ratio: '16:9',
          remoteTaskId: 'r1',
          status: 'succeeded',
          videoUrl: 'https://x/1.mp4',
          error: null,
          createdAt: '2026-08-02T10:00:00Z',
          updatedAt: '2026-08-02T10:00:00Z',
        },
      ],
      code: 200,
    });

    render(<VideoDisplayPage />);

    await waitFor(() => expect(screen.getByText('已完成的视频')).toBeTruthy());
    expect(screen.getByText('已生成')).toBeTruthy();
  });

  it('shows empty state when no tasks', async () => {
    render(<VideoDisplayPage />);
    await waitFor(() => expect(mockListTasks).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/features/workflow/__tests__/VideoDisplayPage.test.tsx`
Expected: FAIL — 无法解析 `../VideoDisplayPage`

- [ ] **Step 3: 实现页面**

Create `frontend/src/features/workflow/VideoDisplayPage.tsx`:

```tsx
/**
 * 视频展示阶段 — 真实实现（MiniMax-H3 文生视频）。
 *
 * 替换原 VideoDisplayMockPage：用户输入 prompt → 异步生成 → 后台轮询推进 →
 * 成功后原生 <video> 播放。历史列表 5s 轮询，直到无未终态任务。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { videoApi, type GenerateInput, type VideoTask } from '../../api/video';

const RESOLUTIONS: GenerateInput['resolution'][] = ['768P', '2K'];
const RATIOS: GenerateInput['ratio'][] = ['21:9', '16:9', '4:3', '1:1', '3:4', '9:16'];
const DURATIONS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
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
  const [resolution, setResolution] = useState<GenerateInput['resolution']>('768P');
  const [duration, setDuration] = useState(5);
  const [ratio, setRatio] = useState<GenerateInput['ratio']>('16:9');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadTasks = useCallback(async () => {
    try {
      const res = await videoApi.listTasks();
      setTasks(res.data);
    } catch {
      /* 静默：下一轮重试 */
    }
  }, []);

  // 轮询：有未终态任务时每 5s 刷新，否则停止
  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

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
      const res = await videoApi.generate({ prompt: prompt.trim(), resolution, duration, ratio });
      setSelectedId(res.data.taskId);
      setPrompt('');
      await loadTasks();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : '生成失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="card"
      style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}
    >
      <div className="card-title">视频展示</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
        输入描述，用 MiniMax-H3 生成方案演示视频
      </div>

      {/* ── 生成表单 ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="描述你想生成的视频画面，例如：手机散热结构分层爆炸图动画"
          maxLength={7000}
          rows={3}
          style={{
            width: '100%',
            resize: 'vertical',
            padding: 10,
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            fontSize: 13,
            fontFamily: 'inherit',
          }}
        />
        <div
          style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', fontSize: 12 }}
        >
          <label style={{ color: 'var(--text-secondary)' }}>
            分辨率{' '}
            <select
              value={resolution}
              onChange={(e) => setResolution(e.target.value as GenerateInput['resolution'])}
            >
              {RESOLUTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label style={{ color: 'var(--text-secondary)' }}>
            时长{' '}
            <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
              {DURATIONS.map((d) => (
                <option key={d} value={d}>
                  {d}s
                </option>
              ))}
            </select>
          </label>
          <label style={{ color: 'var(--text-secondary)' }}>
            宽高比{' '}
            <select
              value={ratio}
              onChange={(e) => setRatio(e.target.value as GenerateInput['ratio'])}
            >
              {RATIOS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={handleGenerate}
            disabled={submitting}
            style={{
              marginLeft: 'auto',
              padding: '8px 18px',
              borderRadius: 8,
              border: 'none',
              background: '#f97316',
              color: '#fff',
              fontSize: 13,
              fontWeight: 600,
              cursor: submitting ? 'not-allowed' : 'pointer',
              opacity: submitting ? 0.6 : 1,
            }}
          >
            {submitting ? '提交中…' : '生成视频'}
          </button>
        </div>
        {formError && <div style={{ fontSize: 12, color: '#ef4444' }}>{formError}</div>}
      </div>

      {/* ── 主播放区 ── */}
      <div
        style={{
          borderRadius: 8,
          overflow: 'hidden',
          border: '1px solid var(--border)',
          background: 'rgba(0,0,0,0.2)',
        }}
      >
        {!selected && (
          <div
            style={{
              height: 280,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-tertiary)',
              fontSize: 13,
            }}
          >
            选择下方任务以预览，或输入描述生成新视频
          </div>
        )}
        {selected && selected.status === 'succeeded' && selected.videoUrl && (
          <video
            key={selected.id}
            src={selected.videoUrl}
            controls
            style={{ width: '100%', display: 'block', maxHeight: 420, background: '#000' }}
          />
        )}
        {selected && NON_TERMINAL.has(selected.status) && (
          <div
            style={{
              height: 280,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
              color: 'var(--text-secondary)',
            }}
          >
            <i
              className="fa-solid fa-circle-notch fa-spin"
              style={{ fontSize: 32, color: '#f97316' }}
            />
            <div style={{ fontSize: 13 }}>
              视频生成中（{STATUS_BADGE[selected.status]?.label}）…
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              生成通常需要数十秒到数分钟，可离开本页，完成后自动出现在列表
            </div>
          </div>
        )}
        {selected && (selected.status === 'failed' || selected.status === 'expired') && (
          <div
            style={{
              height: 280,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              color: '#ef4444',
            }}
          >
            <i className="fa-solid fa-circle-exclamation" style={{ fontSize: 32 }} />
            <div style={{ fontSize: 13 }}>生成失败</div>
            {selected.error && (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{selected.error}</div>
            )}
          </div>
        )}
      </div>

      {/* ── 历史列表 ── */}
      <div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--text-primary)',
            marginBottom: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <i className="fa-solid fa-film" style={{ color: '#f97316', fontSize: 12 }} />
          生成历史
          <span
            style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 4 }}
          >
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
              <div
                key={t.id}
                onClick={() => setSelectedId(t.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: active ? 'rgba(249,115,22,0.06)' : 'rgba(0,0,0,0.2)',
                  border: `1px solid ${active ? 'rgba(249,115,22,0.2)' : 'var(--border)'}`,
                  cursor: 'pointer',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {t.prompt}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {t.resolution} · {t.duration}s · {t.ratio} · {t.createdAt}
                  </div>
                </div>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: badge.bg,
                    color: badge.color,
                    fontSize: 10,
                    flexShrink: 0,
                  }}
                >
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

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/features/workflow/__tests__/VideoDisplayPage.test.tsx`
Expected: PASS（3 个测试）

- [ ] **Step 5: 切换路由并删除 Mock**

修改 `frontend/src/routes/index.tsx`：

把

```typescript
const VideoDisplayMockPage = lazyPage(() => import('../features/workflow/VideoDisplayMockPage'));
```

改为

```typescript
const VideoDisplayPage = lazyPage(() => import('../features/workflow/VideoDisplayPage'));
```

把

```typescript
          { path: 'workflow/video', element: <VideoDisplayMockPage /> },
```

改为

```typescript
          { path: 'workflow/video', element: <VideoDisplayPage /> },
```

然后删除 Mock 文件：

```bash
rm frontend/src/features/workflow/VideoDisplayMockPage.tsx
rm frontend/src/features/workflow/VideoDisplayView.tsx
```

- [ ] **Step 6: 类型检查 + 全量前端测试**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: tsc 无错误；所有前端测试通过

- [ ] **Step 7: 提交**

```bash
git add frontend/src/features/workflow/VideoDisplayPage.tsx \
        frontend/src/features/workflow/__tests__/VideoDisplayPage.test.tsx \
        frontend/src/routes/index.tsx
git add -u frontend/src/features/workflow/
git commit -m "feat(video): replace mock video display with real MiniMax generation"
```

---

## Task 9: 端到端冒烟验证（手动 + 记录）

**Files:** 无代码改动；仅验证与部署记录。

- [ ] **Step 1: 启动后端，确认表创建 + 轮询器启动**

Run: `cd backend && uv run uvicorn app.main:app --port 8000`（或 `make dev`）
Expected: 日志出现「视频生成轮询器已启动」；无启动异常。

- [ ] **Step 2: 管理员录入 MiniMax 供应商与密钥**

在 `/admin/model-providers` 页面新增供应商：

- provider_id: `minimax`
- api_host: `https://api.minimaxi.com`
- api_model: `MiniMax-H3`
- 填入 MiniMax API Key

（密钥未配置时，`generate` 会返回「未配置 MiniMax 密钥」，这是预期行为。）

- [ ] **Step 3: 前端冒烟**

打开 `workflow/video` 页面，输入 prompt，选择参数，点击「生成视频」。
Expected: 列表出现「生成中」任务；数十秒到数分钟后变为「已生成」；点击可播放。

- [ ] **Step 4: 记录部署注意事项到 PR 描述**

在提交 PR 时注明：需管理员先在模型管理页录入 `minimax` 供应商与密钥；视频下载 URL 由 MiniMax 返回（有时效性，历史播放依赖该 URL 有效期）。

---

## Self-Review

**Spec 覆盖核对：**

- 数据模型 video_tasks → Task 1 ✓
- MiniMax 适配器 create/query → Task 2 ✓
- 供应商注册（UI 录入，非种子化）→ Task 9 Step 2 ✓（符合 main.py 约定）
- API 路由 generate/list/get/delete + 参数校验 422 → Task 4 ✓
- 后台轮询器（5s、终态兜底、db_session）→ Task 5 ✓
- main.py 接线 → Task 6 ✓
- 前端替换 Mock + 删 Mock + 原生播放器 + 5s 轮询至无未终态 → Task 8 ✓
- 前端 api 客户端 → Task 7 ✓
- 错误处理（创建失败置 failed、无密钥报错、查询终态同步）→ Task 4（mark_failed）+ Task 5（apply_remote_status）✓
- 测试（适配器/API/轮询器/前端 api/前端组件）→ Task 2/4/5/7/8 ✓

**类型一致性核对：**

- `_row_to_dict` 输出 camelCase（`userId, videoUrl, remoteTaskId, createdAt`）与前端 `VideoTask` 接口字段逐一对齐 ✓
- 适配器 `query_task` 返回 `{status, video_url, error}`，轮询器按此解构 ✓
- `video_task_service` 方法名在 API（Task 4）与轮询器（Task 5）中调用一致：`create/set_remote_task/mark_failed/get/list_by_user/delete/list_active/apply_remote_status` ✓
- `_lease_minimax_key` 在 api/video.py 与 video_poller.py 各自定义（返回 `(plaintext, api_host)`），测试均 patch 对应模块内的同名函数 ✓

**占位符扫描：** 无 TBD/TODO；所有代码步骤含完整代码块；测试步骤含具体断言。
