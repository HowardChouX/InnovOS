"""
测试知识库作业处理器（额外） — prepare_root / delete_subtree / reindex_subtree / check_processing_result

覆盖：
- PrepareRootHandler: 创建子项 → 入队索引作业
- DeleteSubtreeHandler: 递归删除子项+向量+取消作业
- ReindexSubtreeHandler: 重置并重新入队
- CheckProcessingResultHandler: 轮询外部处理器 → 索引
- 删除中的项跳过
- 文件不存在跳过
- 异常处理
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# ═══════════════════════════════════════════════════════════════
#  PrepareRootHandler
# ═══════════════════════════════════════════════════════════════

PREPARE_PATH = "app.services.knowledge_jobs.prepare_root"


@pytest.fixture
def prepare_handler():
    from app.services.knowledge_job_manager import KnowledgeJobManager
    from app.services.knowledge_jobs.prepare_root import PrepareRootHandler

    job_manager = MagicMock(spec=KnowledgeJobManager)
    job_manager.enqueue = AsyncMock(return_value="job-123")
    return PrepareRootHandler(job_manager)


class FakeSignal:
    aborted = False
    def throw_if_aborted(self):
        pass


def make_item(item_id: str, type: str = "directory", data: dict | None = None, status: str = "idle"):
    return {
        "id": item_id,
        "type": type,
        "status": status,
        "data": data or {},
        "error": None,
    }


# ─── PrepareRootHandler ────────────────────────────────────────


@pytest.mark.asyncio
async def test_prepare_root_creates_child_items(prepare_handler):
    """prepare_root 为目录中的文件创建子项。"""
    base_id = "base-1"
    item_id = "dir-1"
    mock_item = make_item(
        item_id,
        "directory",
        {
            "uploadDir": "/tmp/uploads",
            "tree": [
                {"name": "file1.txt", "type": "file", "path": "/tmp/uploads/file1.txt", "originalName": "file1.txt"},
                {"name": "file2.txt", "type": "file", "path": "/tmp/uploads/file2.txt", "originalName": "file2.txt"},
            ],
        },
    )

    with patch(f"{PREPARE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{PREPARE_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{PREPARE_PATH}.KnowledgeItemService.create") as mock_create:
                mock_create.side_effect = [
                    {"id": "child-1"},
                    {"id": "child-2"},
                ]
                with patch(f"{PREPARE_PATH}.KnowledgeItemService.update_status"):
                    with patch("os.path.isdir", return_value=True):
                        with patch("os.path.exists", return_value=True):
                            await prepare_handler.execute(
                                "job-1", {"baseId": base_id, "itemId": item_id}, FakeSignal()
                            )

    # Should create 2 child items
    assert mock_create.call_count == 2
    # Should enqueue 2 index jobs
    assert prepare_handler.job_manager.enqueue.await_count == 2


@pytest.mark.asyncio
async def test_prepare_root_skips_hidden_files(prepare_handler):
    """prepare_root 跳过以 . 开头的隐藏文件。"""
    mock_item = make_item(
        "dir-1",
        "directory",
        {
            "uploadDir": "/tmp/uploads",
            "tree": [
                {"name": ".hidden", "type": "file", "path": "/tmp/uploads/.hidden", "originalName": ""},
                {"name": "visible.txt", "type": "file", "path": "/tmp/uploads/visible.txt", "originalName": "visible.txt"},
            ],
        },
    )

    with patch(f"{PREPARE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{PREPARE_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{PREPARE_PATH}.KnowledgeItemService.create") as mock_create:
                mock_create.return_value = {"id": "child-1"}
                with patch(f"{PREPARE_PATH}.KnowledgeItemService.update_status"):
                    with patch("os.path.isdir", return_value=True):
                        with patch("os.path.exists", return_value=True):
                            await prepare_handler.execute(
                                "job-1", {"baseId": "base-1", "itemId": "dir-1"}, FakeSignal()
                            )

    # Only 1 visible file should be created
    assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_prepare_root_skips_deleting_items(prepare_handler):
    """prepare_root 跳过正在删除的项。"""
    mock_item = make_item("dir-1", "directory", status="deleting")

    with patch(f"{PREPARE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{PREPARE_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{PREPARE_PATH}.KnowledgeItemService.update_status") as mock_update:
                await prepare_handler.execute(
                    "job-1", {"baseId": "base-1", "itemId": "dir-1"}, FakeSignal()
                )

    # 不应有状态变更
    mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_root_empty_tree(prepare_handler):
    """空 tree 将项标记为 completed。"""
    mock_item = make_item("dir-1", "directory", {"uploadDir": "/tmp/uploads", "tree": []})

    with patch(f"{PREPARE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{PREPARE_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{PREPARE_PATH}.KnowledgeItemService.update_status") as mock_update:
                with patch("os.path.isdir", return_value=True):
                    await prepare_handler.execute(
                        "job-1", {"baseId": "base-1", "itemId": "dir-1"}, FakeSignal()
                    )

    mock_update.assert_any_call(1, "dir-1", "completed")


@pytest.mark.asyncio
async def test_prepare_root_processes_subdirectories(prepare_handler):
    """prepare_root 递归处理子目录。"""
    mock_item = make_item(
        "root-dir",
        "directory",
        {
            "uploadDir": "/tmp/uploads",
            "tree": [
                {
                    "name": "subdir",
                    "type": "directory",
                    "children": [
                        {"name": "nested.txt", "type": "file", "path": "/tmp/uploads/subdir/nested.txt", "originalName": "nested.txt"},
                    ],
                },
            ],
        },
    )

    with patch(f"{PREPARE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{PREPARE_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{PREPARE_PATH}.KnowledgeItemService.create") as mock_create:
                mock_create.side_effect = [
                    {"id": "subdir-child"},  # sub directory item
                    {"id": "nested-file"},  # nested file item
                ]
                with patch(f"{PREPARE_PATH}.KnowledgeItemService.update_status"):
                    with patch("os.path.isdir", return_value=True):
                        with patch("os.path.exists", return_value=True):
                            await prepare_handler.execute(
                                "job-1", {"baseId": "base-1", "itemId": "root-dir"}, FakeSignal()
                            )

    # 2 items created: 1 subdir + 1 nested file
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_prepare_root_missing_dir_raises(prepare_handler):
    """uploadDir 不存在时抛出异常。"""
    mock_item = make_item("dir-1", "directory", {"uploadDir": "/nonexistent", "tree": [{"name": "f.txt", "type": "file"}]})

    with patch(f"{PREPARE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{PREPARE_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch("os.path.isdir", return_value=False):
                with pytest.raises(ValueError, match="Upload directory not found"):
                    await prepare_handler.execute(
                        "job-1", {"baseId": "base-1", "itemId": "dir-1"}, FakeSignal()
                    )


@pytest.mark.asyncio
async def test_prepare_root_on_settled_failed(prepare_handler):
    """on_settled 在作业失败时标记。"""
    with patch(f"{PREPARE_PATH}._mark_item_failed") as mock_mark:
        await prepare_handler.on_settled("job-1", "failed", "Error")
        mock_mark.assert_called_once_with("job-1", "Error")


@pytest.mark.asyncio
async def test_prepare_root_on_settled_completed_skips(prepare_handler):
    """on_settled 在完成时不做操作。"""
    with patch(f"{PREPARE_PATH}._mark_item_failed") as mock_mark:
        await prepare_handler.on_settled("job-1", "completed", None)
        mock_mark.assert_not_called()


# ═══════════════════════════════════════════════════════════════
#  DeleteSubtreeHandler
# ═══════════════════════════════════════════════════════════════

DELETE_PATH = "app.services.knowledge_jobs.delete_subtree"


@pytest.fixture
def delete_handler():
    from app.services.knowledge_job_manager import KnowledgeJobManager
    from app.services.knowledge_jobs.delete_subtree import DeleteSubtreeHandler

    job_manager = MagicMock(spec=KnowledgeJobManager)
    job_manager.cancel_job = MagicMock()
    return DeleteSubtreeHandler(job_manager)


@pytest.mark.asyncio
async def test_delete_subtree_deletes_items_and_vectors(delete_handler):
    """delete_subtree 找到子树项、取消作业、删除向量、删除项。"""
    subtree_items = [
        {"id": "root-1", "type": "directory"},
        {"id": "child-1", "type": "file"},
        {"id": "child-2", "type": "file"},
    ]

    with patch(f"{DELETE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{DELETE_PATH}.KnowledgeItemService.get_subtree_items", return_value=subtree_items):
            with patch(f"{DELETE_PATH}.VectorStore") as MockVS:
                mock_store = MagicMock()
                MockVS.return_value = mock_store
                with patch(f"{DELETE_PATH}.KnowledgeItemService.delete_items_by_ids") as mock_delete:
                    await delete_handler.execute(
                        "job-1", {"baseId": "base-1", "rootItemIds": ["root-1"]}, FakeSignal()
                    )

    # All 3 items should be deleted from vector store
    mock_store.delete_by_external_ids.assert_called_once_with(["root-1", "child-1", "child-2"])
    # All items should be deleted from DB
    mock_delete.assert_called_once_with(1, "base-1", ["root-1", "child-1", "child-2"])


@pytest.mark.asyncio
async def test_delete_subtree_empty_ids_returns(delete_handler):
    """rootItemIds 为空时直接返回。"""
    with patch(f"{DELETE_PATH}.KnowledgeItemService.get_subtree_items") as mock_get:
        await delete_handler.execute("job-1", {"baseId": "base-1", "rootItemIds": []}, FakeSignal())
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_delete_subtree_empty_subtree_returns(delete_handler):
    """子树项为空时直接返回。"""
    with patch(f"{DELETE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{DELETE_PATH}.KnowledgeItemService.get_subtree_items", return_value=[]):
            with patch(f"{DELETE_PATH}.VectorStore") as MockVS:
                mock_store = MagicMock()
                MockVS.return_value = mock_store
                with patch(f"{DELETE_PATH}.KnowledgeItemService.delete_items_by_ids") as mock_delete:
                    await delete_handler.execute(
                        "job-1", {"baseId": "base-1", "rootItemIds": ["root-1"]}, FakeSignal()
                    )

    mock_store.delete_by_external_ids.assert_not_called()
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_subtree_cancels_jobs(delete_handler):
    """delete_subtree 取消涉及待删项的作业。"""
    subtree_items = [{"id": "item-1", "type": "file"}]

    # Mock DB to return active jobs that reference the items being deleted
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {"id": "active-job-1", "input_data": '{"itemId": "item-1"}'},
    ]
    mock_db = MagicMock()
    mock_db.execute.return_value = mock_cursor
    mock_db.close = MagicMock()

    with patch(f"{DELETE_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{DELETE_PATH}.KnowledgeItemService.get_subtree_items", return_value=subtree_items):
            with patch(f"{DELETE_PATH}.VectorStore"):
                with patch(f"{DELETE_PATH}.KnowledgeItemService.delete_items_by_ids"):
                    with patch(f"{DELETE_PATH}.get_db", return_value=mock_db):
                        await delete_handler.execute(
                            "job-1", {"baseId": "base-1", "rootItemIds": ["item-1"]}, FakeSignal()
                        )

    # Should cancel jobs for these items
    delete_handler.job_manager.cancel_job.assert_called_once_with("active-job-1", reason="item-deleted")


# ═══════════════════════════════════════════════════════════════
#  ReindexSubtreeHandler
# ═══════════════════════════════════════════════════════════════

REINDEX_PATH = "app.services.knowledge_jobs.reindex_subtree"


@pytest.fixture
def reindex_handler():
    from app.services.knowledge_job_manager import KnowledgeJobManager
    from app.services.knowledge_jobs.reindex_subtree import ReindexSubtreeHandler

    job_manager = MagicMock(spec=KnowledgeJobManager)
    job_manager.enqueue = AsyncMock(return_value="job-abc")
    return ReindexSubtreeHandler(job_manager)


@pytest.mark.asyncio
async def test_reindex_subtree_resets_and_re_enqueues(reindex_handler):
    """reindex_subtree 重置状态并重新入队索引作业。"""
    roots = [
        {"id": "dir-1", "type": "directory", "status": "completed"},
        {"id": "file-1", "type": "file", "status": "completed"},
    ]
    subtree_items = [
        {"id": "dir-1", "type": "directory"},
        {"id": "file-1", "type": "file", "status": "completed"},
        {"id": "child-1", "type": "file", "status": "completed"},
    ]

    def get_by_id_side_effect(user_id, item_id):
        for r in roots:
            if r["id"] == item_id:
                return r
        return {"id": item_id, "type": "file", "status": "completed"}

    with patch(f"{REINDEX_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{REINDEX_PATH}.KnowledgeItemService.get_by_id", side_effect=get_by_id_side_effect):
            with patch(f"{REINDEX_PATH}.KnowledgeItemService.get_subtree_items", return_value=subtree_items):
                with patch(f"{REINDEX_PATH}.KnowledgeItemService.delete_items_by_ids") as mock_delete:
                    with patch(f"{REINDEX_PATH}.VectorStore") as MockVS:
                        mock_store = MagicMock()
                        MockVS.return_value = mock_store
                        with patch(f"{REINDEX_PATH}.KnowledgeItemService.update_status") as mock_update:
                            await reindex_handler.execute(
                                "job-1", {"baseId": "base-1", "rootItemIds": ["dir-1", "file-1"]}, FakeSignal()
                            )

    # Vectors deleted for all leaf items
    mock_store.delete_by_external_ids.assert_called_once()
    # Directory descendants deleted
    mock_delete.assert_called_once()
    # Should enqueue 2 jobs: prepare-root for dir, index-documents for file
    assert reindex_handler.job_manager.enqueue.await_count == 2


@pytest.mark.asyncio
async def test_reindex_subtree_skips_deleting_roots(reindex_handler):
    """reindex_subtree 跳过正在删除的根。"""
    with patch(f"{REINDEX_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{REINDEX_PATH}.KnowledgeItemService.get_by_id", return_value={
            "id": "dir-1", "type": "directory", "status": "deleting"
        }):
            with patch(f"{REINDEX_PATH}.KnowledgeItemService.get_subtree_items") as mock_get:
                await reindex_handler.execute(
                    "job-1", {"baseId": "base-1", "rootItemIds": ["dir-1"]}, FakeSignal()
                )
                mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_reindex_subtree_empty_ids_returns(reindex_handler):
    """rootItemIds 为空时直接返回。"""
    with patch(f"{REINDEX_PATH}.KnowledgeItemService.get_subtree_items") as mock_get:
        await reindex_handler.execute("job-1", {"baseId": "base-1", "rootItemIds": []}, FakeSignal())
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_reindex_subtree_on_settled_failed(reindex_handler):
    """on_settled 失败时标记根项。"""
    with patch(f"{REINDEX_PATH}._mark_active_roots_failed") as mock_mark:
        await reindex_handler.on_settled("job-1", "failed", "Error")
        mock_mark.assert_called_once_with("job-1", "Error")


@pytest.mark.asyncio
async def test_reindex_subtree_on_settled_completed_skips(reindex_handler):
    """on_settled 完成时不做操作。"""
    with patch(f"{REINDEX_PATH}._mark_active_roots_failed") as mock_mark:
        await reindex_handler.on_settled("job-1", "completed", None)
        mock_mark.assert_not_called()


# ═══════════════════════════════════════════════════════════════
#  CheckProcessingResultHandler
# ═══════════════════════════════════════════════════════════════

CHECK_PATH = "app.services.knowledge_jobs.check_processing_result"


@pytest.fixture
def check_handler():
    from app.services.knowledge_job_manager import KnowledgeJobManager
    from app.services.knowledge_lock_manager import KnowledgeLockManager
    from app.services.knowledge_jobs.check_processing_result import CheckProcessingResultHandler

    job_manager = MagicMock(spec=KnowledgeJobManager)
    job_manager.enqueue = AsyncMock(return_value="job-456")
    lock_manager = MagicMock(spec=KnowledgeLockManager)

    async def fake_lock(base_id, task):
        return await task() if asyncio.iscoroutinefunction(task) else task()

    lock_manager.with_base_mutation_lock = fake_lock

    return CheckProcessingResultHandler(job_manager, lock_manager)


@pytest.mark.asyncio
async def test_check_processing_polls_and_indexes(check_handler):
    """check_processing_result 轮询成功后索引内容。"""
    mock_item = make_item("file-1", "file", {"path": "/tmp/test.pdf"}, status="processing")
    mock_processor = MagicMock()
    mock_processor.poll = AsyncMock(return_value={"content": "解析完成的内容", "title": "test"})

    with patch(f"{CHECK_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{CHECK_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{CHECK_PATH}.KnowledgeItemService.update_status") as mock_update:
                with patch(f"{CHECK_PATH}.file_processor_registry.get", return_value=mock_processor):
                    with patch(f"{CHECK_PATH}.KnowledgePipeline") as MockPipeline:
                        pipeline = AsyncMock()
                        pipeline.index_item = AsyncMock(return_value=5)
                        MockPipeline.return_value = pipeline

                        await check_handler.execute(
                            "job-1",
                            {"baseId": "base-1", "itemId": "file-1", "taskId": "task-123", "processorId": "local", "attempt": 0},
                            FakeSignal(),
                        )

    # Status should go through: embedding → completed
    mock_update.assert_any_call(1, "file-1", "embedding", "")
    mock_update.assert_any_call(1, "file-1", "completed", "")
    pipeline.index_item.assert_awaited_once_with("file-1", "解析完成的内容")


@pytest.mark.asyncio
async def test_check_processing_re_enqueues_on_none(check_handler):
    """poll 返回 None 时重新入队。"""
    mock_item = make_item("file-1", "file", status="processing")
    mock_processor = MagicMock()
    mock_processor.poll = AsyncMock(return_value=None)

    with patch(f"{CHECK_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{CHECK_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{CHECK_PATH}.file_processor_registry.get", return_value=mock_processor):
                await check_handler.execute(
                    "job-1",
                    {"baseId": "base-1", "itemId": "file-1", "taskId": "task-123", "processorId": "local", "attempt": 0},
                    FakeSignal(),
                )

    check_handler.job_manager.enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_processing_max_attempts_fails(check_handler):
    """达到最大尝试次数后标记 failed。"""
    mock_item = make_item("file-1", "file", status="processing")
    mock_processor = MagicMock()
    mock_processor.poll = AsyncMock(side_effect=Exception("API error"))

    with patch(f"{CHECK_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{CHECK_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{CHECK_PATH}.KnowledgeItemService.update_status") as mock_update:
                with patch(f"{CHECK_PATH}.file_processor_registry.get", return_value=mock_processor):
                    await check_handler.execute(
                        "job-1",
                        {"baseId": "base-1", "itemId": "file-1", "taskId": "task-123", "processorId": "local", "attempt": 29},
                        FakeSignal(),
                    )

    # 29 >= max_attempts (30), so should fail only if attempt+1 >= max_attempts
    # Actually 29+1 = 30 which equals max_attempts=30, so it should fail
    mock_update.assert_any_call(1, "file-1", "failed", "External processing timed out")


@pytest.mark.asyncio
async def test_check_processing_skips_deleting_items(check_handler):
    """删除中的项跳过处理。"""
    mock_item = make_item("file-1", "file", status="deleting")

    with patch(f"{CHECK_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{CHECK_PATH}.KnowledgeItemService.get_by_id", return_value=mock_item):
            with patch(f"{CHECK_PATH}.KnowledgeItemService.update_status") as mock_update:
                await check_handler.execute(
                    "job-1",
                    {"baseId": "base-1", "itemId": "file-1", "taskId": "task-123", "processorId": "local", "attempt": 0},
                    FakeSignal(),
                )

    mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_check_processing_missing_item_raises(check_handler):
    """项不存在时抛出异常。"""
    with patch(f"{CHECK_PATH}._get_user_id_from_base", return_value=1):
        with patch(f"{CHECK_PATH}.KnowledgeItemService.get_by_id", return_value=None):
            with pytest.raises(ValueError, match="Knowledge item not found"):
                await check_handler.execute(
                    "job-1",
                    {"baseId": "base-1", "itemId": "nonexistent", "taskId": "task-123", "processorId": "local", "attempt": 0},
                    FakeSignal(),
                )


@pytest.mark.asyncio
async def test_check_processing_on_settled_failed(check_handler):
    """on_settled 失败时标记。"""
    with patch(f"{CHECK_PATH}._mark_item_failed") as mock_mark:
        await check_handler.on_settled("job-1", "failed", "Error")
        mock_mark.assert_called_once_with("job-1", "Error")


@pytest.mark.asyncio
async def test_check_processing_on_settled_completed_skips(check_handler):
    """on_settled 完成时不做操作。"""
    with patch(f"{CHECK_PATH}._mark_item_failed") as mock_mark:
        await check_handler.on_settled("job-1", "completed", None)
        mock_mark.assert_not_called()
