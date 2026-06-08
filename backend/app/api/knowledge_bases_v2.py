"""
知识库 API — 参考 CherryStudio DataApi 知识处理器

提供 SQLite 支持的知识库端点：
- 知识库列表/详情读取
- 知识库元数据/配置更新
- 知识库内知识项读取

DataApi 仅暴露由数据库层满足的操作。
运行时/索引变更（创建、删除、恢复、重新索引向量存储工件）
由 KnowledgeOrchestrationService 协调。
"""
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.services.knowledge_service_v3 import KnowledgeBaseService, KnowledgeItemService
from app.services.knowledge_orchestration import knowledge_orchestration_service
from app.models.knowledge import (
    CreateKnowledgeBaseDto,
    UpdateKnowledgeBaseDto,
    CreateKnowledgeItemDto,
)
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


class CreateBaseInput(BaseModel):
    name: str
    groupId: Optional[str] = None
    dimensions: Optional[int] = None
    embeddingModelId: Optional[str] = None
    status: str = "completed"
    error: Optional[str] = None
    rerankModelId: Optional[str] = None
    fileProcessorId: Optional[str] = None
    chunkSize: int = 1024
    chunkOverlap: int = 200
    threshold: Optional[float] = None
    documentCount: Optional[int] = None
    searchMode: str = "hybrid"
    hybridAlpha: Optional[float] = None


class UpdateBaseInput(BaseModel):
    name: Optional[str] = None
    groupId: Optional[str] = None
    rerankModelId: Optional[str] = None
    fileProcessorId: Optional[str] = None
    chunkSize: Optional[int] = None
    chunkOverlap: Optional[int] = None
    threshold: Optional[float] = None
    documentCount: Optional[int] = None
    searchMode: Optional[str] = None
    hybridAlpha: Optional[float] = None
    status: Optional[str] = None
    error: Optional[str] = None
    dimensions: Optional[int] = None
    embeddingModelId: Optional[str] = None


@router.get("")
def list_bases(page: int = 1, limit: int = 20, user: dict = Depends(get_current_user)):
    """列出用户的知识库"""
    result = KnowledgeBaseService.list_bases(user["id"], page=page, limit=limit)
    return {"data": result, "message": "success", "code": 200}


@router.post("")
async def create_base(body: CreateBaseInput, user: dict = Depends(get_current_user)):
    """创建知识库"""
    data = body.model_dump(exclude_unset=True)
    result = await knowledge_orchestration_service.create_base(user["id"], data)
    return {"data": result, "message": "created", "code": 200}


@router.get("/{base_id}")
def get_base(base_id: str, user: dict = Depends(get_current_user)):
    """获取单个知识库"""
    result = KnowledgeBaseService.get_by_id(user["id"], base_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "success", "code": 200}


@router.patch("/{base_id}")
def update_base(base_id: str, body: UpdateBaseInput, user: dict = Depends(get_current_user)):
    """更新知识库"""
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    result = KnowledgeBaseService.update_base(user["id"], base_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "updated", "code": 200}


@router.delete("/{base_id}")
async def delete_base(base_id: str, user: dict = Depends(get_current_user)):
    """删除知识库"""
    ok = await knowledge_orchestration_service.delete_base(user["id"], base_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"message": "deleted", "code": 200}


# ============================================================================
# 知识项 API
# ============================================================================

@router.get("/{base_id}/items")
def list_items(
    base_id: str,
    page: int = 1,
    limit: int = 20,
    type: str = "",
    groupId: str = "",
    user: dict = Depends(get_current_user),
):
    """列出知识库中的知识项"""
    result = KnowledgeItemService.list_items(
        user["id"], base_id, page=page, limit=limit,
        item_type=type, group_id=groupId,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "success", "code": 200}


@router.post("/{base_id}/items")
async def create_item(base_id: str, body: CreateItemInput, user: dict = Depends(get_current_user)):
    """添加知识项"""
    result = await knowledge_orchestration_service.add_items(
        user["id"], base_id, [body.model_dump()]
    )
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result[0] if result else None, "message": "created", "code": 200}


@router.get("/items/{item_id}")
def get_item(item_id: str, user: dict = Depends(get_current_user)):
    """获取单个知识项"""
    result = KnowledgeItemService.get_by_id(user["id"], item_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识项不存在")
    return {"data": result, "message": "success", "code": 200}


@router.patch("/items/{item_id}")
def update_item(item_id: str, body: UpdateItemInput, user: dict = Depends(get_current_user)):
    """更新知识项"""
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    # 简化实现：只支持 status/error 更新
    if "status" in data:
        result = KnowledgeItemService.update_status(
            user["id"], item_id, data["status"], data.get("error", "")
        )
        if not result:
            raise HTTPException(status_code=404, detail="知识项不存在")
        return {"data": result, "message": "updated", "code": 200}
    raise HTTPException(status_code=400, detail="不支持的更新字段")


@router.delete("/items/{item_id}")
def delete_item(item_id: str, user: dict = Depends(get_current_user)):
    """删除知识项"""
    ok = KnowledgeItemService.delete_item(user["id"], item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识项不存在")
    return {"message": "deleted", "code": 200}


# ============================================================================
# 搜索 API
# ============================================================================

@router.get("/search")
async def search_knowledge(user: dict = Depends(get_current_user), q: str = "", base_id: str = "", limit: int = 10):
    """搜索知识库"""
    if not q:
        raise HTTPException(status_code=400, detail="搜索查询不能为空")
    
    try:
        results = await knowledge_orchestration_service.search(user["id"], base_id, q, limit)
        return {"data": results, "total": len(results), "message": "success", "code": 200}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")
