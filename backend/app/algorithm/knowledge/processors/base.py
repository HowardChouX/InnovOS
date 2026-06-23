"""文件处理器基类 — 定义同步/异步处理器的通用接口。"""

from typing import Protocol


class FileProcessor(Protocol):
    """文件处理器协议。

    支持两种模式：
    - **同步 (sync)**: process() 直接返回解析结果。
    - **异步 (async)**: submit() 提交任务 → poll() 轮询结果。
    """

    def is_async(self) -> bool:
        """是否为异步（外部 API）处理器。"""
        ...

    async def process(self, file_path: str, file_name: str) -> dict:
        """同步解析文件，返回 {"content": str, "title": str}。

        仅对同步处理器有效。异步处理器可以抛出 NotImplementedError。
        """
        ...

    async def submit(self, file_path: str) -> str:
        """提交文件给外部处理器，返回 task_id。

        仅对异步处理器有效。同步处理器可以抛出 NotImplementedError。
        """
        ...

    async def poll(self, task_id: str) -> dict | None:
        """轮询外部处理结果。

        返回 {"content": str, "title": str} 表示完成，
        返回 None 表示仍在处理中。

        仅对异步处理器有效。同步处理器可以抛出 NotImplementedError。
        """
        ...


class SyncFileProcessor:
    """同步文件处理基类 — 默认使用 file_parser.py 解析。"""

    def is_async(self) -> bool:
        return False

    async def process(self, file_path: str, file_name: str) -> dict:
        raise NotImplementedError

    async def submit(self, file_path: str) -> str:
        raise NotImplementedError("同步处理器不支持 submit()")

    async def poll(self, task_id: str) -> dict | None:
        raise NotImplementedError("同步处理器不支持 poll()")
