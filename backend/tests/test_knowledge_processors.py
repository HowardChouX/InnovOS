"""
测试文件处理器注册表和本地处理器 — knowledge/processors/

覆盖：
- _FileProcessorRegistry 注册和查找
- file_processor_registry 全局单例
- LocalFileProcessor 处理 PDF/DOCX/TXT/MD
- 未知文件类型处理
- get() 回退到默认本地处理器
- 未注册 processor_id 返回默认
- 同步/异步区分
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

PROC_PATH = "app.algorithm.knowledge.processors"


# ─── _FileProcessorRegistry ────────────────────────────────────


def test_registry_register_and_get():
    """注册表 register/get 正常工作。"""
    from app.algorithm.knowledge.processors import _FileProcessorRegistry

    registry = _FileProcessorRegistry()
    mock_processor = MagicMock()
    registry.register("custom", mock_processor)

    retrieved = registry.get("custom")
    assert retrieved is mock_processor


def test_registry_get_default():
    """get(None) 返回默认本地处理器。"""
    from app.algorithm.knowledge.processors import _FileProcessorRegistry

    registry = _FileProcessorRegistry()
    result = registry.get(None)
    assert result is not None


def test_registry_get_unknown_falls_back():
    """get(unknown_id) 返回默认本地处理器。"""
    from app.algorithm.knowledge.processors import _FileProcessorRegistry

    registry = _FileProcessorRegistry()
    result = registry.get("nonexistent-processor")
    assert result is not None


def test_registry_list_ids():
    """list_ids 返回注册的 ID 列表。"""
    from app.algorithm.knowledge.processors import _FileProcessorRegistry

    registry = _FileProcessorRegistry()
    ids = registry.list_ids()
    assert "local" in ids


def test_registry_default_has_local():
    """默认注册了 local 处理器。"""
    from app.algorithm.knowledge.processors import file_processor_registry

    processor = file_processor_registry.get("local")
    assert processor is not None


def test_registry_register_replaces():
    """register 替换已存在的处理器。"""
    from app.algorithm.knowledge.processors import _FileProcessorRegistry

    registry = _FileProcessorRegistry()
    old = MagicMock()
    new = MagicMock()
    registry._register("local", old)
    registry.register("local", new)
    assert registry.get("local") is new


# ─── LocalFileProcessor ────────────────────────────────────────


@pytest.mark.asyncio
async def test_local_processor_process_calls_parse_file():
    """LocalFileProcessor.process 调用 parse_file。"""
    from app.algorithm.knowledge.processors.local import LocalFileProcessor

    processor = LocalFileProcessor()
    # Patch the local parse_file reference in the processors.local module
    with patch("app.algorithm.knowledge.processors.local.parse_file") as mock_parse:
        mock_parse.return_value = {"content": "文件内容", "title": "测试文档", "type": "text"}
        result = await processor.process("/tmp/test.pdf", "test.pdf")

    assert result["content"] == "文件内容"
    assert result["title"] == "测试文档"
    mock_parse.assert_called_once_with("/tmp/test.pdf")


@pytest.mark.asyncio
async def test_local_processor_process_txt():
    """LocalFileProcessor 处理 .txt 文件。"""
    from app.algorithm.knowledge.processors.local import LocalFileProcessor

    processor = LocalFileProcessor()
    with patch("app.algorithm.knowledge.processors.local.parse_file") as mock_parse:
        mock_parse.return_value = {"content": "纯文本内容", "title": "notes.txt"}
        result = await processor.process("/tmp/notes.txt", "notes.txt")

    assert result["content"] == "纯文本内容"


@pytest.mark.asyncio
async def test_local_processor_process_md():
    """LocalFileProcessor 处理 .md 文件。"""
    from app.algorithm.knowledge.processors.local import LocalFileProcessor

    processor = LocalFileProcessor()
    with patch("app.algorithm.knowledge.processors.local.parse_file") as mock_parse:
        mock_parse.return_value = {"content": "# Markdown 标题", "title": "readme.md"}
        result = await processor.process("/tmp/readme.md", "readme.md")

    assert "# Markdown" in result["content"]


@pytest.mark.asyncio
async def test_local_processor_process_docx():
    """LocalFileProcessor 处理 .docx 文件。"""
    from app.algorithm.knowledge.processors.local import LocalFileProcessor

    processor = LocalFileProcessor()
    with patch("app.algorithm.knowledge.processors.local.parse_file") as mock_parse:
        mock_parse.return_value = {"content": "Word 文档内容", "title": "report.docx"}
        result = await processor.process("/tmp/report.docx", "report.docx")

    assert result["content"] == "Word 文档内容"


def test_local_processor_is_async_false():
    """LocalFileProcessor.is_async 返回 False。"""
    from app.algorithm.knowledge.processors.local import LocalFileProcessor

    processor = LocalFileProcessor()
    assert processor.is_async() is False


@pytest.mark.asyncio
async def test_local_processor_submit_raises():
    """LocalFileProcessor.submit 抛出 NotImplementedError。"""
    from app.algorithm.knowledge.processors.local import LocalFileProcessor

    processor = LocalFileProcessor()
    with pytest.raises(NotImplementedError):
        await processor.submit("/tmp/test.pdf")


@pytest.mark.asyncio
async def test_local_processor_poll_raises():
    """LocalFileProcessor.poll 抛出 NotImplementedError。"""
    from app.algorithm.knowledge.processors.local import LocalFileProcessor

    processor = LocalFileProcessor()
    with pytest.raises(NotImplementedError):
        await processor.poll("task-123")


# ─── SyncFileProcessor ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_file_processor_defaults():
    """SyncFileProcessor 默认方法行为。"""
    from app.algorithm.knowledge.processors.base import SyncFileProcessor

    processor = SyncFileProcessor()
    assert processor.is_async() is False
    with pytest.raises(NotImplementedError):
        await processor.process("/tmp/f.pdf", "f.pdf")
    with pytest.raises(NotImplementedError):
        await processor.submit("/tmp/f.pdf")
    with pytest.raises(NotImplementedError):
        await processor.poll("task-id")


# ─── FileProcessor Protocol ────────────────────────────────────


def test_processor_protocol():
    """FileProcessor protocol 可被鸭子类型实现。"""
    from app.algorithm.knowledge.processors.base import FileProcessor

    # A class that implements the protocol must have all methods
    class MockProcessor:
        def is_async(self):
            return False

        async def process(self, file_path, file_name):
            return {"content": "", "title": ""}

        async def submit(self, file_path):
            return "task-id"

        async def poll(self, task_id):
            return {"content": "", "title": ""}

    mp = MockProcessor()
    # Should not raise TypeError
    _: FileProcessor = mp
    assert mp.is_async() is False


# ─── file_processor_registry 全局单例 ─────────────────────────


def test_global_registry_contains_local():
    """全局 registry 包含 local 处理器。"""
    from app.algorithm.knowledge.processors import file_processor_registry

    ids = file_processor_registry.list_ids()
    assert "local" in ids


def test_global_registry_get_local():
    """全局 registry.get('local') 返回处理器。"""
    from app.algorithm.knowledge.processors import file_processor_registry

    processor = file_processor_registry.get("local")
    assert processor is not None
    assert callable(getattr(processor, "process", None))
