"""文件处理器注册表 — 管理文件处理器实例。

默认注册 `local` 处理器，使用本地 file_parser 进行同步解析。
可通过 `register()` 注册外部/异步处理器。
"""

from app.algorithm.knowledge.processors.base import FileProcessor
from app.algorithm.knowledge.processors.local import LOCAL_PROCESSOR_ID, LocalFileProcessor, local_processor


class _FileProcessorRegistry:
    """文件处理器注册表。

    特性：
    - 按 processor_id 注册/查找处理器实例
    - get(None) 或 get(unknown_id) 返回默认本地处理器
    """

    def __init__(self):
        self._processors: dict[str, FileProcessor] = {}
        self._default: FileProcessor = local_processor
        self._register(LOCAL_PROCESSOR_ID, LocalFileProcessor())

    def _register(self, processor_id: str, processor: FileProcessor) -> None:
        self._processors[processor_id] = processor

    def register(self, processor_id: str, processor: FileProcessor) -> None:
        """注册外部处理器。"""
        self._processors[processor_id] = processor

    def get(self, processor_id: str | None) -> FileProcessor:
        """获取处理器实例。

        Args:
            processor_id: 处理器 ID。为 None 或未注册时返回默认本地处理器。
        Returns:
            FileProcessor 实例
        """
        if processor_id and processor_id in self._processors:
            return self._processors[processor_id]
        return self._default

    def list_ids(self) -> list[str]:
        return list(self._processors.keys())


# 全局单例
file_processor_registry = _FileProcessorRegistry()

__all__ = [
    "file_processor_registry",
    "FileProcessor",
    "LocalFileProcessor",
    "LOCAL_PROCESSOR_ID",
]
