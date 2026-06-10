import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.auth import get_current_user
from app.database import get_db
from app.services.knowledge_job_manager import (
    JOB_TYPE_PREPARE_ROOT,
    knowledge_queue_name,
    knowledge_idempotency_key,
)
from app.services.knowledge_orchestration_service import knowledge_orchestration_service
from app.services.knowledge_service_v2 import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService

logger = logging.getLogger(__name__)

# 生产环境持久化上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "uploads")
UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)

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


class MultiBaseSearchInput(BaseModel):
    query: str
    baseIds: list[str]
    topK: int = 10


class RestoreBaseInput(BaseModel):
    sourceBaseId: str
    name: str
    embeddingModelId: str
    dimensions: Optional[int] = None


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


def _build_directory_tree(files_meta: list[dict]) -> list[dict]:
    """从平铺的文件列表构建目录树。

    输入: [{"name": "a/b/c.txt", ...}, {"name": "a/d.md", ...}]
    输出: [{"type": "dir", "name": "a", "children": [
            {"type": "file", "name": "c.txt", ...},
            {"type": "file", "name": "d.md", ...}]}]
    """
    tree: dict[str, dict] = {}
    for entry in files_meta:
        rel_path = entry["name"]
        parts = rel_path.replace("\\", "/").split("/")
        curr = tree
        for i, part in enumerate(parts):
            if part in (".", "..") or part.startswith("."):
                break  # skip hidden
            if i == len(parts) - 1:
                # 叶子节点 → 文件
                curr[part] = {"type": "file", "name": part, "path": entry["path"],
                              "originalName": rel_path, "size": entry.get("size", 0)}
            else:
                # 中间节点 → 目录
                if part not in curr:
                    curr[part] = {"type": "dir", "name": part, "children": {}}
                curr = curr[part]["children"]

    def _to_list(node: dict) -> list[dict]:
        result = []
        for name, val in sorted(node.items()):
            if val["type"] == "dir":
                children = _to_list(val["children"])
                if children:  # 空目录跳过
                    result.append({"type": "directory", "name": name, "children": children})
            else:
                result.append({"type": "file", "name": val["name"], "path": val["path"],
                               "originalName": val["originalName"], "size": val["size"]})
        return result

    return _to_list(tree)


@router.post("/{base_id}/items/import-directory")
async def import_directory(
    base_id: str,
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
):
    """导入文件夹：接收浏览器上传的文件列表，保存到持久化目录，创建目录知识项并调度处理。"""
    if not files:
        raise HTTPException(status_code=400, detail="未选择任何文件")

    # 过滤支持的文件类型，跳过隐藏文件
    supported_extensions = {
        '.pdf', '.docx', '.doc', '.txt', '.md', '.csv',
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
        '.rb', '.php', '.c', '.cpp', '.h', '.hpp',
        '.sql', '.yaml', '.yml', '.toml', '.json', '.xml',
        '.sh', '.bash', '.zsh', '.env', '.ini', '.cfg',
    }
    valid_files = []
    for f in files:
        if not f.filename:
            continue
        basename = os.path.basename(f.filename)
        if basename.startswith("."):
            continue  # 跳过隐藏文件
        ext = os.path.splitext(f.filename)[1].lower()
        if ext in supported_extensions:
            valid_files.append(f)

    if not valid_files:
        raise HTTPException(status_code=400, detail="没有支持的文件格式（.pdf .docx .txt .md .csv）")

    # 创建持久化目录：uploads/{user_id}/{base_id}/{item_id}/
    item_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOAD_DIR, str(user["id"]), base_id, item_id)
    os.makedirs(upload_dir, exist_ok=True)

    saved_files = []
    for file in valid_files:
        content = await file.read()
        rel_path = file.filename or "unnamed"
        # 保留原始相对路径结构（webkitdirectory 会保留相对路径）
        safe_path = rel_path.replace("..", "_")
        target_path = os.path.join(upload_dir, safe_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(content)
        saved_files.append({"name": rel_path, "path": target_path, "size": len(content)})

    # 构建目录树结构
    tree = _build_directory_tree(saved_files)

    # 提取根目录名称（从第一个文件的相对路径首段）
    root_name = "directory"
    if saved_files:
        first_parts = saved_files[0]["name"].replace("\\", "/").split("/", 1)
        if len(first_parts) > 1:
            root_name = first_parts[0]
    # 创建 directory 类型的 knowledge_item
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.execute(
        """INSERT INTO knowledge_items
           (id, base_id, group_id, type, data, status, error, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (item_id, base_id, None, "directory",
         json.dumps({"source": root_name, "uploadDir": upload_dir, "tree": tree, "files": saved_files, "count": len(saved_files)}),
         "idle", None, now, now),
    )
    db.commit()
    db.close()

    # 通过 JobManager 调度处理
    await knowledge_orchestration_service.job_manager.enqueue(
        JOB_TYPE_PREPARE_ROOT,
        {"baseId": base_id, "itemId": item_id},
        queue=knowledge_queue_name(base_id),
        idempotency_key=knowledge_idempotency_key("import", base_id, item_id),
    )

    logger.info("Directory import started: %d files -> item %s (tree=%d nodes)", len(saved_files), item_id, len(tree))
    return {"data": {"id": item_id, "count": len(saved_files)}, "message": "import started", "code": 200}


@router.post("/{base_id}/restore")
async def restore_base(base_id: str, body: RestoreBaseInput, user: dict = Depends(get_current_user)):
    """从失败的源知识库恢复：克隆配置并重新导入所有项"""
    source_base = KnowledgeBaseService.get_by_id(user["id"], body.sourceBaseId)
    if not source_base:
        raise HTTPException(status_code=404, detail="源知识库不存在")

    new_base_id = str(uuid.uuid4())
    restore_dto = {
        "name": body.name,
        "embeddingModelId": body.embeddingModelId,
        "dimensions": body.dimensions,
    }
    new_base = KnowledgeBaseService.restore(user["id"], body.sourceBaseId, new_base_id, restore_dto)

    # 复制源知识库的所有项
    items = KnowledgeItemService.get_items_by_base_id(user["id"], body.sourceBaseId)
    new_items = []
    for item in items:
        new_items.append({
            "id": str(uuid.uuid4()),
            "type": item["type"],
            "data": item["data"],
            "groupId": item.get("groupId"),
        })

    await knowledge_orchestration_service.add_items(user["id"], new_base_id, new_items)
    return {"data": new_base, "message": "知识库恢复成功", "code": 200}


@router.post("/{base_id}/items/{item_id}/reindex")
async def reindex_item(base_id: str, item_id: str, user: dict = Depends(get_current_user)):
    """重新索引知识项 — 编排服务验证状态(canReindex)+入队后台作业，对齐 cherry-studio"""
    await knowledge_orchestration_service.reindex_items(user["id"], base_id, [item_id])
    return {"message": "重索引已开始", "code": 200}


@router.post("/{base_id}/items/{item_id}/process-url")
async def process_url_item(base_id: str, item_id: str, user: dict = Depends(get_current_user)):
    """获取 URL 知识项的内容并存储"""
    item = KnowledgeItemService.get_by_id(user["id"], item_id)
    if not item:
        raise HTTPException(status_code=404, detail="知识项不存在")
    if item["type"] != "url":
        raise HTTPException(status_code=400, detail="仅支持 URL 类型的知识项")

    data = item["data"]
    if not isinstance(data, dict):
        data = {}
    url = data.get("url") or data.get("sourceUrl")
    if not url:
        raise HTTPException(status_code=400, detail="知识项中没有 URL")

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            content = resp.text
    except ImportError:
        error_msg = "URL processing requires httpx. Install with: pip install httpx"
        db.execute(
            "UPDATE knowledge_items SET error=?, updated_at=? WHERE id=?",
            (error_msg, now, item_id),
        )
        db.commit()
        db.close()
        return {"data": None, "message": error_msg, "code": 400}
    except Exception as e:
        error_msg = f"URL 获取失败: {str(e)}"
        db.execute(
            "UPDATE knowledge_items SET error=?, updated_at=? WHERE id=?",
            (error_msg, now, item_id),
        )
        db.commit()
        db.close()
        return {"data": None, "message": error_msg, "code": 400}

    data["fetchedContent"] = content
    data["fetchedAt"] = now
    db.execute(
        "UPDATE knowledge_items SET data=?, status=?, error=?, updated_at=? WHERE id=?",
        (json.dumps(data), "completed", None, now, item_id),
    )
    db.commit()
    db.close()
    return {"data": {"id": item_id, "url": url, "contentLength": len(content)}, "message": "URL 内容已获取", "code": 200}


@router.post("/search")
async def multi_base_search(body: MultiBaseSearchInput, user: dict = Depends(get_current_user)):
    """跨多个知识库搜索，返回去重并按分数降序的结果"""
    results = await asyncio.gather(*[
        knowledge_orchestration_service.search(user["id"], base_id, body.query, top_k=body.topK)
        for base_id in body.baseIds
    ], return_exceptions=True)

    seen: dict[str, dict] = {}
    for base_id, batch in zip(body.baseIds, results):
        if isinstance(batch, BaseException):
            logger.warning("Search failed for base %s: %s", base_id, batch)
            continue
        assert isinstance(batch, list), f"unexpected result type: {type(batch)}"
        for item in batch:
            text = item.get("text", "")
            score = item.get("score", 0)
            if text not in seen or seen[text]["score"] < score:
                seen[text] = {"text": text, "score": score, "source": item.get("source", ""), "baseId": base_id}

    merged = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return {"data": merged, "message": "success", "code": 200}
