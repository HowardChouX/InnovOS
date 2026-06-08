"""
知识库编排服务 — 参考 CherryStudio KnowledgeOrchestrationService

职责：
- 持有知识库创建/删除/恢复/索引工作流
- 管理知识项的生命周期
- 协调向量存储操作
- 处理异步任务队列
"""
import asyncio
import logging
from typing import Optional
from app.database import get_db
from app.services.knowledge_service_v3 import KnowledgeBaseService, KnowledgeItemService
from app.algorithm.knowledge.retriever import KnowledgeRetriever

logger = logging.getLogger(__name__)


class KnowledgeOrchestrationService:
    """
    知识库编排服务 — 对齐 CherryStudio KnowledgeOrchestrationService
    
    职责：
    - 持有知识库创建/删除/恢复工作流
    - 注册 Knowledge JobManager handlers
    - 持有 KnowledgeLockManager
    - 协调向量存储和文件管理器
    """

    def __init__(self):
        self._lock_manager = KnowledgeLockManager()

    async def create_base(self, user_id: int, data: dict) -> dict:
        """
        创建知识库
        
        流程：
        1. 创建 SQLite 行
        2. 初始化向量存储
        3. 返回创建的知识库
        """
        base = KnowledgeBaseService.create_base(user_id, data)
        logger.info(f"创建知识库: {base['id']}")
        return base

    async def delete_base(self, user_id: int, base_id: str) -> bool:
        """
        删除知识库
        
        流程：
        1. 取消活跃的 Knowledge 作业
        2. 在 base 变更锁下删除向量存储工件
        3. 删除 SQLite 基行
        """
        # 获取锁
        async with self._lock_manager.acquire(base_id):
            # 删除向量存储（这里简化处理）
            # TODO: 实现向量存储删除
            
            # 删除数据库记录
            result = KnowledgeBaseService.delete_base(user_id, base_id)
            if result:
                logger.info(f"删除知识库: {base_id}")
            return result

    async def add_items(self, user_id: int, base_id: str, items: list[dict]) -> list[dict]:
        """
        添加知识项
        
        流程：
        1. 创建 knowledge_item 行
        2. 标记根项为 processing
        3. 排队索引作业
        """
        created_items = []
        
        for item_data in items:
            # 创建知识项
            item = KnowledgeItemService.create_item(user_id, base_id, item_data)
            if item:
                created_items.append(item)
                logger.info(f"添加知识项: {item['id']} 类型: {item['type']}")
                
                # 异步处理索引
                asyncio.create_task(self._process_item(user_id, item))
        
        return created_items

    async def _process_item(self, user_id: int, item: dict):
        """处理单个知识项"""
        try:
            # 标记为 processing
            KnowledgeItemService.update_status(user_id, item["id"], "processing")
            
            # 根据类型处理
            item_type = item["type"]
            data = item["data"]
            
            if item_type == "file":
                await self._process_file_item(user_id, item, data)
            elif item_type == "url":
                await self._process_url_item(user_id, item, data)
            elif item_type == "note":
                await self._process_note_item(user_id, item, data)
            elif item_type == "directory":
                await self._process_directory_item(user_id, item, data)
            
            # 标记为 completed
            KnowledgeItemService.update_status(user_id, item["id"], "completed")
            
        except Exception as e:
            logger.error(f"处理知识项失败: {item['id']} 错误: {e}")
            KnowledgeItemService.update_status(user_id, item["id"], "failed", str(e))

    async def _process_file_item(self, user_id: int, item: dict, data: dict):
        """处理文件类型知识项"""
        # TODO: 实现文件处理
        # 1. 读取文件内容
        # 2. 解析文件
        # 3. 分块
        # 4. 嵌入
        # 5. 存储向量
        pass

    async def _process_url_item(self, user_id: int, item: dict, data: dict):
        """处理 URL 类型知识项"""
        # TODO: 实现 URL 处理
        pass

    async def _process_note_item(self, user_id: int, item: dict, data: dict):
        """处理笔记类型知识项"""
        # TODO: 实现笔记处理
        pass

    async def _process_directory_item(self, user_id: int, item: dict, data: dict):
        """处理目录类型知识项"""
        # TODO: 实现目录处理
        pass

    async def search(self, user_id: int, base_id: str, query: str, limit: int = 10) -> list[dict]:
        """
        搜索知识库
        
        流程：
        1. 拒绝失败的知识库
        2. 拒绝没有可搜索 token 的查询
        3. 解析并运行查询的嵌入模型
        4. 查询向量存储
        5. 过滤结果
        6. 重排（如果配置了重排模型）
        7. 应用相关性阈值并分配排名
        """
        # 验证知识库存在且状态正常
        base = KnowledgeBaseService.get_by_id(user_id, base_id)
        if not base:
            raise ValueError("知识库不存在")
        if base["status"] == "failed":
            raise ValueError("知识库状态失败")
        
        # 执行搜索
        retriever = KnowledgeRetriever(user_id)
        results = await retriever.search(query, limit)
        
        return results

    async def reindex_items(self, user_id: int, base_id: str, item_ids: list[str]) -> bool:
        """
        重新索引知识项
        
        流程：
        1. 加载请求的项并将后代折叠到顶层根
        2. 验证每个选定的子树项都是终态：completed 或 failed
        3. 排队重新索引作业
        4. 在 base 变更锁下，删除旧向量，重置选定根为 preparing 或 processing
        5. 通过工作流服务调度每个选定根
        """
        # TODO: 实现重新索引
        pass


class KnowledgeLockManager:
    """
    知识库锁管理器 — 对齐 CherryStudio KnowledgeLockManager
    
    职责：
    - 序列化同库变更和向量清理
    """
    
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
    
    def _get_lock(self, base_id: str) -> asyncio.Lock:
        """获取或创建指定知识库的锁"""
        if base_id not in self._locks:
            self._locks[base_id] = asyncio.Lock()
        return self._locks[base_id]
    
    async def acquire(self, base_id: str):
        """获取锁"""
        return self._get_lock(base_id).acquire()
    
    def release(self, base_id: str):
        """释放锁"""
        self._get_lock(base_id).release()


# 全局实例
knowledge_orchestration_service = KnowledgeOrchestrationService()
