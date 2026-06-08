from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.services.knowledge_service_v2 import KnowledgeBaseService
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
    result = KnowledgeBaseService.list_bases(user["id"], page=page, limit=limit)
    return {"data": result, "message": "success", "code": 200}


@router.post("")
def create_base(body: CreateBaseInput, user: dict = Depends(get_current_user)):
    data = body.model_dump(exclude_unset=True)
    result = KnowledgeBaseService.create_base(user["id"], data)
    return {"data": result, "message": "created", "code": 200}


@router.get("/{base_id}")
def get_base(base_id: str, user: dict = Depends(get_current_user)):
    result = KnowledgeBaseService.get_by_id(user["id"], base_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "success", "code": 200}


@router.patch("/{base_id}")
def update_base(base_id: str, body: UpdateBaseInput, user: dict = Depends(get_current_user)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    result = KnowledgeBaseService.update_base(user["id"], base_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "updated", "code": 200}


@router.delete("/{base_id}")
def delete_base(base_id: str, user: dict = Depends(get_current_user)):
    ok = KnowledgeBaseService.delete_base(user["id"], base_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"message": "deleted", "code": 200}
