"""
Knowledge Lock Manager — 完全复现 CherryStudio KnowledgeLockManager

职责：
- 每个知识库的互斥锁
- 序列化同库变更
"""
import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")


class KnowledgeLockManager:
    """知识库锁管理器 — 完全对齐 CherryStudio KnowledgeLockManager"""

    def __init__(self):
        self._base_mutexes: dict[str, asyncio.Lock] = {}

    def _get_mutex(self, base_id: str) -> asyncio.Lock:
        """获取或创建指定知识库的锁"""
        if base_id not in self._base_mutexes:
            self._base_mutexes[base_id] = asyncio.Lock()
        return self._base_mutexes[base_id]

    async def with_base_mutation_lock(self, base_id: str, task: Callable[[], T]) -> T:
        """在基变更锁下执行任务"""
        mutex = self._get_mutex(base_id)
        async with mutex:
            try:
                return await task()
            finally:
                self._delete_idle_mutex(base_id, mutex)

    def _delete_idle_mutex(self, base_id: str, mutex: asyncio.Lock) -> None:
        """删除空闲的互斥锁"""
        if not mutex.locked() and self._base_mutexes.get(base_id) is mutex:
            del self._base_mutexes[base_id]
