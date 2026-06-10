"""
File Processor Registry — resolves file processors by fileProcessorId
"""
import logging
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class FileProcessor(Protocol):
    """File processor interface"""

    async def process(self, file_path: str, file_name: str) -> dict:
        """Process a file synchronously — returns {content, title, type}"""
        ...

    async def submit(self, file_path: str) -> str:
        """Submit file for async processing — returns task_id.
        Only needed for async processors. Default raises NotImplementedError."""
        ...

    async def poll(self, task_id: str) -> Optional[dict]:
        """Poll async processing status.
        Returns None if still processing, dict {content, title} when done.
        Only needed for async processors."""
        ...

    def is_async(self) -> bool:
        """Whether this processor is async (needs polling)"""
        ...


class FileProcessorRegistry:
    """Registry of file processors"""

    def __init__(self):
        self._processors: dict[str, "FileProcessor"] = {}
        self._register_defaults()

    def _register_defaults(self):
        from .default import DefaultFileProcessor

        default = DefaultFileProcessor()
        self.register("default", default)
        self.register("", default)
        self.register(None, default)

    def register(self, processor_id: Optional[str], processor: "FileProcessor") -> None:
        self._processors[str(processor_id) if processor_id is not None else ""] = processor

    def get(self, processor_id: Optional[str]) -> "FileProcessor":
        pid = str(processor_id) if processor_id is not None else ""
        if pid in self._processors:
            return self._processors[pid]
        # Try to create external processor
        if pid and pid not in (None, "", "default"):
            from .external import ExternalFileProcessor

            ext = ExternalFileProcessor(pid)
            self._processors[pid] = ext
            return ext
        return self._processors[""]  # fallback


# Singleton
file_processor_registry = FileProcessorRegistry()
