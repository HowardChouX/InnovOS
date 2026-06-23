"""本地文件处理器 — 使用 app.algorithm.file_parser 进行同步解析。"""

import logging

from app.algorithm.file_parser import parse_file
from app.algorithm.knowledge.processors.base import SyncFileProcessor

logger = logging.getLogger(__name__)

LOCAL_PROCESSOR_ID = "local"


class LocalFileProcessor(SyncFileProcessor):
    """本地同步文件处理器，支持 PDF/DOCX/TXT/MD/CSV。"""

    async def process(self, file_path: str, file_name: str) -> dict:
        """使用 file_parser.parse_file 同步解析文件。"""
        result = parse_file(file_path)
        return {
            "content": result.get("content", ""),
            "title": result.get("title", file_name),
        }


# 单例
local_processor = LocalFileProcessor()
