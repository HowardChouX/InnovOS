import json
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.auth import get_current_user
from app.database import get_db
from app.utils import utc_iso
from app.algorithm.file_parser import parse_file
from app.algorithm.knowledge.retriever import get_retriever
from app.algorithm.knowledge.pipeline import KnowledgePipeline, get_embedding_api_config
from app.services.knowledge_service_v2 import KnowledgeItemService
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_DIR = "/tmp/innovos-knowledge-uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class CreateItemInput(BaseModel):
    type: str  # file, url, note, directory
    groupId: Optional[str] = None
    data: dict


class UpdateItemInput(BaseModel):
    status: Optional[str] = None
    error: Optional[str] = None
    data: Optional[dict] = None


# ─── 文件上传 ──────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    base_id: str = Form(""),
    user: dict = Depends(get_current_user)
):
    """上传文件 → 解析 → 存储为知识项"""
    file_path = os.path.join(UPLOAD_DIR, f"{user['id']}_{file.filename}")
    content_bytes = await file.read()
    with open(file_path, "wb") as f:
        f.write(content_bytes)

    pipeline = KnowledgePipeline(user["id"], base_id=base_id)
    result = await pipeline.process_file(file_path, file.filename or "untitled")

    try:
        os.remove(file_path)
    except:
        pass

    # 创建 knowledge_item 记录
    if base_id:
        item = KnowledgeItemService.create_item(
            user["id"], base_id,
            {
                "type": "file",
                "data": {
                    "source": file.filename or "untitled",
                    "fileEntryId": result.get("doc_id", ""),
                },
                "status": "completed",
            }
        )
        return {"data": item, "message": "导入成功", "code": 200}

    return {"data": result, "message": "导入成功", "code": 200}


# ─── 知识项 CRUD ─────────────────────────────────────

@router.get("/bases/{base_id}/items")
def list_items(
    base_id: str,
    page: int = 1,
    limit: int = 20,
    type: str = "",
    groupId: str = "",
    user: dict = Depends(get_current_user),
):
    result = KnowledgeItemService.list_items(
        user["id"], base_id, page=page, limit=limit,
        item_type=type, group_id=groupId,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "success", "code": 200}


@router.post("/bases/{base_id}/items")
def create_item(base_id: str, body: CreateItemInput, user: dict = Depends(get_current_user)):
    result = KnowledgeItemService.create_item(user["id"], base_id, body.model_dump())
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "created", "code": 200}


@router.get("/items/{item_id}")
def get_item(item_id: str, user: dict = Depends(get_current_user)):
    result = KnowledgeItemService.get_by_id(user["id"], item_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识项不存在")
    return {"data": result, "message": "success", "code": 200}


@router.patch("/items/{item_id}")
def update_item(item_id: str, body: UpdateItemInput, user: dict = Depends(get_current_user)):
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
    ok = KnowledgeItemService.delete_item(user["id"], item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识项不存在")
    return {"message": "deleted", "code": 200}


# ─── 搜索 ───────────────────────────────────────────

@router.get("/search")
async def search_knowledge(user: dict = Depends(get_current_user), q: str = "", base_id: str = "", limit: int = 10):
    """RAG 检索"""
    db = get_db()
    if q:
        pipeline = KnowledgePipeline(user["id"])
        results = []
        try:
            results = await pipeline.search(q, limit)
        except Exception:
            pass
        if results:
            db.close()
            return {"data": results, "total": len(results), "message": "success", "code": 200}

    # LIKE 降级
    rows = db.execute(
        """SELECT id, title, content, category, tags, source, doc_type, updated_at FROM knowledge_docs
           WHERE user_id=? AND is_active=1 AND (title LIKE ? OR content LIKE ?)
           ORDER BY updated_at DESC LIMIT ?""",
        (user["id"], f"%{q}%", f"%{q}%", limit),
    ).fetchall() if q else db.execute(
        "SELECT id, title, content, category, tags, source, doc_type, updated_at FROM knowledge_docs WHERE user_id=? AND is_active=1 ORDER BY updated_at DESC LIMIT ?",
        (user["id"], limit),
    ).fetchall()
    db.close()

    data = [{"id": str(r["id"]), "title": r["title"], "content": r["content"], "category": r["category"], "tags": json.loads(r["tags"]), "source": r["source"], "docType": r["doc_type"], "relevance": 0, "updatedAt": utc_iso(r["updated_at"])} for r in rows]
    return {"data": data, "total": len(data), "message": "success", "code": 200}


# ─── 嵌入模型配置 ─────────────────────────────────────

@router.get("/embed-config")
def get_embed_config(user: dict = Depends(get_current_user)):
    config = get_embedding_api_config()
    return {"data": config, "message": "success", "code": 200}


# ─── 分组 API ────────────────────────────────────────

@router.get("/groups")
def list_groups(user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM knowledge_groups WHERE user_id=? ORDER BY updated_at DESC",
        (user["id"],),
    ).fetchall()
    db.close()
    return {
        "data": [
            {
                "id": r["id"], "name": r["name"],
                "createdAt": utc_iso(r["created_at"]), "updatedAt": utc_iso(r["updated_at"]),
            }
            for r in rows
        ],
        "message": "success", "code": 200,
    }


@router.post("/groups")
def create_group(body: dict, user: dict = Depends(get_current_user)):
    import uuid
    db = get_db()
    gid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO knowledge_groups (id, user_id, name) VALUES (?, ?, ?)",
        (gid, user["id"], body.get("name", "未命名分组")),
    )
    db.commit()
    row = db.execute("SELECT * FROM knowledge_groups WHERE id=?", (gid,)).fetchone()
    db.close()
    return {
        "data": {
            "id": row["id"], "name": row["name"],
            "createdAt": utc_iso(row["created_at"]), "updatedAt": utc_iso(row["updated_at"]),
        },
        "message": "created", "code": 200,
    }


@router.delete("/groups/{group_id}")
def delete_group(group_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM knowledge_groups WHERE id=? AND user_id=?", (group_id, user["id"]))
    # 解除知识库的分组关联
    db.execute("UPDATE knowledge_bases SET group_id=NULL WHERE group_id=? AND user_id=?", (group_id, user["id"]))
    db.commit()
    db.close()
    return {"message": "deleted", "code": 200}
