"""
测试知识库作业处理器 — IndexDocumentsHandler 的文件/笔记/URL 处理

覆盖：
- 笔记项：提取内容 → 索引 → completed
- URL 项：抓取内容 → 保存 → 索引 → completed
- 文件项：解析 → 保存 → 索引 → completed
- 删除中的项：跳过
- 未知类型：标记 completed
- 文件不存在：标记 failed
- URL 获取失败：标记 failed
"""
import json
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, mock_open
from datetime import datetime, timezone

JOB_PATH = "app.services.knowledge_jobs.index_documents"


@pytest.fixture(autouse=True)
def _patch_get_db(monkeypatch):
    """Mock DB so job handler doesn't need real database."""
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchone.return_value = {"user_id": 1}
    monkeypatch.setattr("app.database.get_db", lambda: mock_db)
    return mock_db


@pytest.fixture
def handler():
    """Create IndexDocumentsHandler with mocked dependencies."""
    from app.services.knowledge_job_manager import KnowledgeJobManager
    from app.services.knowledge_lock_manager import KnowledgeLockManager
    from app.services.knowledge_jobs.index_documents import IndexDocumentsHandler

    job_manager = MagicMock(spec=KnowledgeJobManager)
    lock_manager = MagicMock(spec=KnowledgeLockManager)

    async def noop_lock(base_id, task):
        return await task()

    lock_manager.with_base_mutation_lock = noop_lock
    job_manager.enqueue = AsyncMock(return_value="job-123")

    return IndexDocumentsHandler(job_manager, lock_manager)


def make_item(item_id: str, type: str, data: dict, status: str = "idle"):
    """Create a mock knowledge item dict."""
    return {
        "id": item_id,
        "base_id": "base-1",
        "type": type,
        "data": data,
        "status": status,
        "error": None,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


class FakeSignal:
    """Mock signal that never aborts."""
    aborted = False
    def throw_if_aborted(self):
        pass


# ─── Note item tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_note_processing_extracts_content_and_indexes(handler):
    """笔记项提取 data.content → pipeline.index_item → completed"""
    item = make_item("note-1", "note", {"content": "手机发热怎么办", "source": "测试笔记"})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item) as mock_get:
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status") as mock_update:
            with patch(f"{JOB_PATH}.KnowledgePipeline") as MockPipeline:
                pipeline_instance = AsyncMock()
                pipeline_instance.index_item = AsyncMock(return_value=3)
                MockPipeline.return_value = pipeline_instance

                await handler.execute("job-1", {"baseId": "base-1", "itemId": "note-1"}, FakeSignal())

    # 状态: idle → reading → completed
    status_calls = [call.args for call in mock_update.call_args_list]
    status_seq = [call[2] for call in status_calls if len(call) >= 3]
    assert "reading" in status_seq
    assert "completed" in status_seq
    pipeline_instance.index_item.assert_awaited_once()
    text_arg = pipeline_instance.index_item.call_args[0][1]
    assert "手机发热" in text_arg


@pytest.mark.asyncio
async def test_note_empty_content_still_indexes(handler):
    """笔记内容为空时 pipeline.index_item 仍被调用（可能返回0）"""
    item = make_item("note-2", "note", {"content": ""})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status"):
            with patch(f"{JOB_PATH}.KnowledgePipeline") as MockPipeline:
                pipeline_instance = AsyncMock()
                pipeline_instance.index_item = AsyncMock(return_value=0)
                MockPipeline.return_value = pipeline_instance

                await handler.execute("job-2", {"baseId": "base-1", "itemId": "note-2"}, FakeSignal())

    pipeline_instance.index_item.assert_awaited_once()


# ─── URL item tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_url_processing_fetches_and_indexes(handler):
    """URL 项通过 httpx 抓取 → 保存 → 索引 → completed"""
    item = make_item("url-1", "url", {"url": "https://example.com/doc"})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status"):
            with patch(f"{JOB_PATH}.KnowledgePipeline") as MockPipeline:
                pipeline_instance = AsyncMock()
                pipeline_instance.index_item = AsyncMock(return_value=2)
                MockPipeline.return_value = pipeline_instance

                # Mock httpx response
                mock_resp = AsyncMock()
                mock_resp.status_code = 200
                mock_resp.text = "<html>手机散热方案</html>"
                mock_resp.raise_for_status = AsyncMock()

                async def mock_get(*args, **kwargs):
                    return mock_resp

                with patch("httpx.AsyncClient") as MockClient:
                    client_instance = AsyncMock()
                    client_instance.__aenter__.return_value.get = mock_get
                    MockClient.return_value.__aenter__.return_value = client_instance

                    await handler.execute("job-3", {"baseId": "base-1", "itemId": "url-1"}, FakeSignal())

    pipeline_instance.index_item.assert_awaited_once()
    text_arg = pipeline_instance.index_item.call_args[0][1]
    assert "手机散热方案" in text_arg


@pytest.mark.asyncio
async def test_url_without_url_marks_failed(handler):
    """URL 项没有 url 字段 → failed"""
    item = make_item("url-2", "url", {})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status") as mock_update:
            await handler.execute("job-4", {"baseId": "base-1", "itemId": "url-2"}, FakeSignal())

    status_calls = [call.args for call in mock_update.call_args_list]
    last_status = status_calls[-1][2] if status_calls else ""
    assert last_status == "failed"


@pytest.mark.asyncio
async def test_url_fetch_failure_marks_failed(handler):
    """URL 获取失败（httpx 异常）→ failed"""
    item = make_item("url-3", "url", {"url": "https://invalid.example.com"})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status") as mock_update:
            with patch("httpx.AsyncClient") as MockClient:
                client_instance = AsyncMock()
                async def mock_get(*args, **kwargs):
                    raise Exception("Connection refused")
                client_instance.__aenter__.return_value.get = mock_get
                MockClient.return_value.__aenter__.return_value = client_instance

                await handler.execute("job-5", {"baseId": "base-1", "itemId": "url-3"}, FakeSignal())

    status_calls = [call.args for call in mock_update.call_args_list]
    last_status = status_calls[-1][2] if status_calls else ""
    assert last_status == "failed"


# ─── Deleting item test ──────────────────────────────────────

@pytest.mark.asyncio
async def test_deleting_item_is_skipped(handler):
    """删除中的项不会被处理"""
    item = make_item("del-1", "note", {"content": "test"}, status="deleting")

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status") as mock_update:
            await handler.execute("job-6", {"baseId": "base-1", "itemId": "del-1"}, FakeSignal())

    # 不应有状态变更
    assert mock_update.call_count == 0


# ─── Unknown type test ────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_type_is_marked_completed(handler):
    """未知类型项标记为 completed"""
    item = make_item("unk-1", "image", {"file": "photo.jpg"})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status") as mock_update:
            await handler.execute("job-7", {"baseId": "base-1", "itemId": "unk-1"}, FakeSignal())

    status_calls = [call.args for call in mock_update.call_args_list]
    last_status = status_calls[-1][2] if status_calls else ""
    assert last_status == "completed"


# ─── File item tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_file_processing_parses_and_indexes(handler):
    """文件项解析 → 保存 parsedContent → 索引 → completed"""
    item = make_item("file-1", "file", {"path": "/tmp/test.txt", "source": "test.txt"})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status") as mock_update:
            with patch(f"{JOB_PATH}.KnowledgePipeline") as MockPipeline:
                pipeline_instance = AsyncMock()
                pipeline_instance.index_item = AsyncMock(return_value=5)
                MockPipeline.return_value = pipeline_instance

                # Mock file processor
                mock_processor = MagicMock()
                mock_processor.is_async.return_value = False
                mock_processor.process = AsyncMock(return_value={
                    "content": "文件解析内容",
                    "title": "test.txt",
                })

                with patch(f"{JOB_PATH}.file_processor_registry.get", return_value=mock_processor):
                    with patch("os.path.exists", return_value=True):
                        await handler.execute("job-8", {"baseId": "base-1", "itemId": "file-1"}, FakeSignal())

    pipeline_instance.index_item.assert_awaited_once()
    text_arg = pipeline_instance.index_item.call_args[0][1]
    assert "文件解析内容" in text_arg

    # 验证状态: reading → completed
    status_calls = [call.args for call in mock_update.call_args_list]
    status_seq = [call[2] for call in status_calls if len(call) >= 3]
    assert "reading" in status_seq
    assert "completed" in status_seq


@pytest.mark.asyncio
async def test_file_not_found_marks_failed(handler):
    """文件路径不存在 → failed"""
    item = make_item("file-2", "file", {"path": "/nonexistent/file.pdf"})

    with patch(f"{JOB_PATH}.KnowledgeItemService.get_by_id", return_value=item):
        with patch(f"{JOB_PATH}.KnowledgeItemService.update_status") as mock_update:
            with patch("os.path.exists", return_value=False):
                await handler.execute("job-9", {"baseId": "base-1", "itemId": "file-2"}, FakeSignal())

    status_calls = [call.args for call in mock_update.call_args_list]
    last_status = status_calls[-1][2] if status_calls else ""
    assert last_status == "failed"


# ─── on_settled test ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_on_settled_failed_marks_item_failed(handler):
    """on_settled 在作业失败时标记知识项为 failed"""
    with patch(f"{JOB_PATH}._mark_item_failed") as mock_mark:
        await handler.on_settled("job-10", "failed", "Embedding API error")
        mock_mark.assert_called_once_with("job-10", "Embedding API error")


@pytest.mark.asyncio
async def test_on_settled_completed_does_nothing(handler):
    """on_settled 在作业完成时不操作"""
    with patch(f"{JOB_PATH}._mark_item_failed") as mock_mark:
        await handler.on_settled("job-11", "completed", None)
        mock_mark.assert_not_called()
