import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.audit import log_audit
from app.auth import get_current_user
from app.database import get_db
from app.services.file_storage_service import file_storage
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService
from app.services.knowledge_job_manager import (
    JOB_TYPE_PREPARE_ROOT,
    knowledge_idempotency_key,
    knowledge_queue_name,
)
from app.services.knowledge_orchestration_service import knowledge_orchestration_service

logger = logging.getLogger(__name__)

# 生产环境持久化上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "uploads")
UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── File upload limits ──────────────────────────────────────────
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB per batch
SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
}

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


class CreateBaseInput(BaseModel):
    name: str
    groupId: str | None = None
    dimensions: int | None = None
    embeddingModelId: str | None = None
    status: str = "completed"
    error: str | None = None
    rerankModelId: str | None = None
    fileProcessorId: str | None = None
    chunkSize: int = 1024
    chunkOverlap: int = 200
    threshold: float | None = None
    documentCount: int | None = None
    searchMode: str = "hybrid"
    hybridAlpha: float | None = None


class MultiBaseSearchInput(BaseModel):
    query: str
    baseIds: list[str]
    topK: int = 10


class RestoreBaseInput(BaseModel):
    sourceBaseId: str
    name: str
    embeddingModelId: str
    dimensions: int | None = None


class UpdateBaseInput(BaseModel):
    name: str | None = None
    groupId: str | None = None
    rerankModelId: str | None = None
    fileProcessorId: str | None = None
    chunkSize: int | None = None
    chunkOverlap: int | None = None
    threshold: float | None = None
    documentCount: int | None = None
    searchMode: str | None = None
    hybridAlpha: float | None = None
    status: str | None = None
    error: str | None = None
    dimensions: int | None = None
    embeddingModelId: str | None = None


@router.get("")
def list_bases(page: int = 1, limit: int = 20, user: dict = Depends(get_current_user)):
    result = KnowledgeBaseService.list(user["id"], page=page, limit=limit)
    return {"data": result, "message": "success", "code": 200}


@router.post("")
def create_base(body: CreateBaseInput, user: dict = Depends(get_current_user)):
    data = body.model_dump(exclude_unset=True)
    result = KnowledgeBaseService.create(user["id"], data)
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
    result = KnowledgeBaseService.update(user["id"], base_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"data": result, "message": "updated", "code": 200}


@router.delete("/{base_id}")
def delete_base(base_id: str, request: Request, user: dict = Depends(get_current_user)):
    log_audit(
        user["id"],
        user.get("username", ""),
        "kb.delete",
        "knowledge_base",
        base_id,
        {},
        request.client.host if request.client else "",
    )
    ok = KnowledgeBaseService.delete(user["id"], base_id)
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
                curr[part] = {
                    "type": "file",
                    "name": part,
                    "path": entry["path"],
                    "originalName": rel_path,
                    "size": entry.get("size", 0),
                }
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
                result.append(
                    {
                        "type": "file",
                        "name": val["name"],
                        "path": val["path"],
                        "originalName": val["originalName"],
                        "size": val["size"],
                    }
                )
        return result

    return _to_list(tree)


@router.post("/{base_id}/items/import-directory")
async def import_directory(
    base_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
):
    """导入文件夹：接收浏览器上传的文件列表，保存到持久化目录，创建目录知识项并调度处理。"""
    if not files:
        raise HTTPException(status_code=400, detail="未选择任何文件")

    # 验证知识库归属权
    db_check = get_db()
    base_owner = db_check.execute(
        "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?",
        (base_id, user["id"]),
    ).fetchone()
    db_check.close()
    if not base_owner:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 过滤支持的文件类型，跳过隐藏文件
    supported_extensions = {
        ".pdf",
        ".docx",
        ".doc",
        ".txt",
        ".md",
        ".csv",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".sql",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".xml",
        ".sh",
        ".bash",
        ".zsh",
        ".env",
        ".ini",
        ".cfg",
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
    total_size = 0
    for file in valid_files:
        content = await file.read()
        # ── File size validation ──
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件 {file.filename} 超过大小限制 (50MB)")
        total_size += len(content)
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(status_code=400, detail="总文件大小超过限制 (500MB)")
        # ── MIME type hint check ──
        ext = os.path.splitext(file.filename or "")[1].lower()
        expected_mime = SUPPORTED_MIME_TYPES.get(ext)
        if (
            expected_mime
            and file.content_type
            and file.content_type != expected_mime
            and file.content_type != "application/octet-stream"
        ):
            # 仅对明显不匹配发警告（不阻止上传），application/octet-stream 是浏览器常见回退
            logger.warning(
                "MIME type mismatch for %s: expected %s, got %s", file.filename, expected_mime, file.content_type
            )

        rel_path = file.filename or "unnamed"
        # 路径穿越防护：去除目录组件
        rel_path = os.path.basename(rel_path)
        safe_path = rel_path.replace("..", "_")

        # 尝试上传到 MinIO/S3（如果已配置）
        if file_storage.enabled:
            s3_key = await file_storage.upload(user["id"], safe_path, content, base_id=base_id, item_id=item_id)
            if s3_key:
                saved_files.append({"name": rel_path, "path": s3_key, "size": len(content)})
                continue
            logger.warning("S3 upload failed for %s, falling back to local", safe_path)

        # 回退到本地文件系统
        target_path = os.path.join(upload_dir, safe_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(content)
        saved_files.append({"name": rel_path, "path": target_path, "size": len(content)})

    # Audit log for the import operation
    log_audit(
        user["id"],
        user.get("username", ""),
        "kb.import",
        "knowledge_base",
        base_id,
        {"fileCount": len(saved_files), "totalSize": total_size},
        request.client.host if request.client else "",
    )

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
        (
            item_id,
            base_id,
            None,
            "directory",
            json.dumps(
                {
                    "source": root_name,
                    "uploadDir": upload_dir,
                    "tree": tree,
                    "files": saved_files,
                    "count": len(saved_files),
                }
            ),
            "idle",
            None,
            now,
            now,
        ),
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
        new_items.append(
            {
                "id": str(uuid.uuid4()),
                "type": item["type"],
                "data": item["data"],
                "groupId": item.get("groupId"),
            }
        )

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
    return {
        "data": {"id": item_id, "url": url, "contentLength": len(content)},
        "message": "URL 内容已获取",
        "code": 200,
    }


@router.post("/search")
async def multi_base_search(body: MultiBaseSearchInput, user: dict = Depends(get_current_user)):
    """跨多个知识库搜索，返回去重并按分数降序的结果"""
    results = await asyncio.gather(
        *[
            knowledge_orchestration_service.search(user["id"], base_id, body.query, top_k=body.topK)
            for base_id in body.baseIds
        ],
        return_exceptions=True,
    )

    seen: dict[str, dict] = {}
    for base_id, batch in zip(body.baseIds, results, strict=False):
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
