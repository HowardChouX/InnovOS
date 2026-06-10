"""Default file processor — wraps parse_file()"""
import logging
from typing import Optional

from app.algorithm.file_parser import parse_file

logger = logging.getLogger(__name__)


class DefaultFileProcessor:
    """Default file processor using local file parsing"""

    async def process(self, file_path: str, file_name: str) -> dict:
        """Parse file locally using parse_file()"""
        import asyncio

        result = await asyncio.to_thread(parse_file, file_path)
        logger.info(
            "Default processor parsed %s: type=%s len=%d",
            file_name,
            result.get("type", ""),
            len(result.get("content", "")),
        )
        return result

    async def submit(self, file_path: str) -> str:
        raise NotImplementedError("Default processor does not support async submission")

    async def poll(self, task_id: str) -> Optional[dict]:
        raise NotImplementedError("Default processor does not support polling")

    def is_async(self) -> bool:
        return False
