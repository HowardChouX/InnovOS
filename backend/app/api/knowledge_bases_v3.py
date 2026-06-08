"""
Knowledge API — 完全复现 CherryStudio DataApi 知识处理器

提供 SQLite 支持的知识库端点：
- 知识库列表/详情读取
- 知识库元数据/配置更新
- 知识库内知识项读取
"""
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService
from app.services.knowledge_orchestration_service import knowledge_orchestration_service
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


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


class CreateItemInput(BaseModel):
    type: str
    groupId: Optional[str] = None
    data: dict


@router.get("")
def list_bases(page: int = 1, limit: int = 20):
    """列出知识库"""
    result = KnowledgeBaseService.list(page=page, limit=limit)
    return {"data": result, "message": "success", "code": 200}


@router.get("/{base_id}")
def get_base(base_id: str):
    """获取单个知识库"""
    result = KnowledgeBaseService.get_by_id(base_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "success", "code": 200}


@router.patch("/{base_id}")
def update_base(base_id: str, body: UpdateBaseInput):
    """更新知识库"""
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    result = KnowledgeBaseService.update(base_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "updated", "code": 200}


@router.delete("/{base_id}")
async def delete_base(base_id: str):
    """删除知识库"""
    try:
        await knowledge_orchestration_service.delete_base(base_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": "deleted", "code": 200}


@router.get("/{base_id}/items")
def list_items(
    base_id: str,
    page: int = 1,
    limit: int = 20,
    type: str = None,
    groupId: str = None,
):
    """列出知识项"""
    result = KnowledgeItemService.list(base_id, page=page, limit=limit, type=type, groupId=groupId)
    if result is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "success", "code": 200}


@router.get("/items/{item_id}")
def get_item(item_id: str):
    """获取单个知识项"""
    result = KnowledgeItemService.get_by_id(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识项不存在")
    return {"data": result, "message": "success", "code": 200}


@router.delete("/items/{item_id}")
def delete_item(item_id: str):
    """删除知识项"""
    ok = KnowledgeItemService.delete(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识项不存在")
    return {"message": "deleted", "code": 200}
