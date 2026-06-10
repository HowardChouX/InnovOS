import json
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.auth import get_current_user
from app.database import get_db
from app.utils import utc_iso
from app.algorithm.knowledge.retriever import get_retriever
from app.algorithm.knowledge.pipeline import KnowledgePipeline
from app.services.knowledge_service_v2 import KnowledgeItemService
from app.services.file_storage_service import file_storage
from app.services.knowledge_job_manager import (
    JOB_TYPE_INDEX_DOCUMENTS,
    knowledge_queue_name,
    knowledge_idempotency_key,
)
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

# 生产环境持久化上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "uploads")
UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)
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
    """上传文件 → 持久化存储 → 解析 → 存储为知识项"""
    content_bytes = await file.read()
    filename = file.filename or "untitled"

    # 1. 持久化存储到 MinIO/S3（如果已配置）
    s3_key = await file_storage.upload(user["id"], filename, content_bytes)

    # 2. 写入持久化目录用于解析
    user_upload_dir = os.path.join(UPLOAD_DIR, str(user["id"]))
    os.makedirs(user_upload_dir, exist_ok=True)
    file_path = os.path.join(user_upload_dir, f"{base_id or 'default'}_{filename}")
    with open(file_path, "wb") as f:
        f.write(content_bytes)

    # 3. 创建 knowledge_item 记录
    if not base_id:
        return {"data": {"path": file_path}, "message": "文件已保存", "code": 200}

    item_data = {
        "source": filename,
        "path": file_path,
    }
    if s3_key:
        item_data["s3Key"] = s3_key

    item = KnowledgeItemService.create_item(
        user["id"], base_id,
        {
            "type": "file",
            "data": item_data,
            "status": "processing",
        }
    )

    # 4. 异步索引（通过 job queue，与 URL/Note 统一）
    from app.services.knowledge_orchestration_service import knowledge_orchestration_service

    await knowledge_orchestration_service.job_manager.enqueue(
        JOB_TYPE_INDEX_DOCUMENTS,
        {"baseId": base_id, "itemId": item["id"]},
        queue=knowledge_queue_name(base_id),
        idempotency_key=knowledge_idempotency_key("add", base_id, item["id"]),
    )
    logger.info(f"文件 {filename} 已入队异步索引: item_id={item['id']}")

    return {"data": item, "message": "导入成功", "code": 200}


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
async def create_item(base_id: str, body: CreateItemInput, user: dict = Depends(get_current_user)):
    """创建知识项 — 通过编排服务统一管理生命周期（对齐 cherry-studio workflow）"""
    from app.services.knowledge_orchestration_service import knowledge_orchestration_service

    item_dict = body.model_dump()
    items_list = [item_dict]

    await knowledge_orchestration_service.add_items(user["id"], base_id, items_list)

    return {"data": items_list, "message": "created", "code": 200}


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
        from app.services.knowledge_item_service import KnowledgeItemService

        pipeline = KnowledgePipeline(user["id"], base_id=base_id)
        raw_results = []
        try:
            raw_results = await pipeline.search(q, limit)
        except Exception as e:
            logger.warning("向量检索失败: %s", e)
        if raw_results:
            # 映射为前端期望的 KnowledgeSearchResult 格式
            mapped = []
            for i, r in enumerate(raw_results):
                item_id = r.get("item_id", "")
                # 获取知识项信息
                item = KnowledgeItemService.get_by_id(user["id"], item_id) if item_id else None
                source = ""
                if item:
                    item_data = json.loads(item["data"]) if isinstance(item["data"], str) else item["data"]
                    source = (item_data.get("url") or item_data.get("source") or item_data.get("originalName") or "")

                mapped.append({
                    "chunkId": r.get("id", ""),
                    "pageContent": r.get("text", ""),
                    "score": r.get("score", 0),
                    "scoreKind": "relevance",
                    "rank": i + 1,
                    "metadata": {
                        "source": source,
                        "chunkIndex": r.get("chunk_index", 0),
                        "tokenCount": len(r.get("text", "").split()),
                    },
                })
            db.close()
            return {"data": mapped, "total": len(mapped), "message": "success", "code": 200}

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


# ─── 文件下载 ─────────────────────────────────────────

@router.get("/files/{item_id}/download")
async def download_item_file(
    item_id: str,
    user: dict = Depends(get_current_user),
):
    """下载知识项关联的原始文件（从 MinIO 获取）。"""
    # 查找知识项，获取 S3 key
    item = KnowledgeItemService.get_by_id(user["id"], item_id)
    if not item:
        raise HTTPException(status_code=404, detail="知识项不存在")

    data = item.get("data", {})
    if isinstance(data, str):
        data = json.loads(data)
    s3_key = data.get("s3Key") if isinstance(data, dict) else None

    if not s3_key or not file_storage.enabled:
        raise HTTPException(status_code=404, detail="文件不存在或未持久化存储")

    content = await file_storage.download(s3_key)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在或无法访问")

    filename = data.get("source", "download")
    from fastapi.responses import Response

    return Response(
        content=content,
        media_type=file_storage._guess_mime(filename),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
