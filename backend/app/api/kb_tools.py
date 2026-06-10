"""
AI Agent KB Tools API — 参考 CherryStudio KnowledgeSearchTool / KnowledgeListTool
提供 kb__search 和 kb__list 端点供 AI agent 使用
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.database import get_db
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_item_service import KnowledgeItemService
from app.services.knowledge_orchestration_service import knowledge_orchestration_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kb-tools", tags=["kb-tools"])

SAMPLE_LIMIT = 8
NOTE_SNIPPET_MAX_CHARS = 80


# ── 来源提取 ──────────────────────────────────────────────────────

def derive_sample_source(item: dict) -> Optional[str]:
    """从知识项数据中提取样本来源（文件名/URL/路径/笔记首行）"""
    data = item.get("data", {}) or {}
    item_type = item.get("type", "")

    if item_type == "file":
        file_data = data.get("file") or {}
        value = (
            (file_data.get("origin_name") or "").strip()
            or (file_data.get("name") or "").strip()
            or (data.get("source") or "").strip()
            or (data.get("fileEntryId") or "").strip()
        )
        return value if value else None

    elif item_type == "url":
        url = (data.get("url") or "").strip()
        return url if url else None

    elif item_type == "directory":
        path = (data.get("path") or "").strip()
        return path if path else None

    elif item_type == "note":
        content = data.get("content") or ""
        for line in content.split("\n"):
            trimmed = line.strip()
            if trimmed:
                if len(trimmed) > NOTE_SNIPPET_MAX_CHARS:
                    return trimmed[:NOTE_SNIPPET_MAX_CHARS - 1] + "…"
                return trimmed
        return None

    return None


def derive_source_from_item(item: dict) -> str:
    """从知识项中提取来源文本（搜索结果中使用的来源字段）"""
    source = derive_sample_source(item)
    return source or item.get("id", "")


def matches_query(item: dict, lowered: str) -> bool:
    """检查项的名称或样本来源是否匹配查询子串"""
    if lowered in item.get("name", "").lower():
        return True
    return any(lowered in s.lower() for s in item.get("sampleSources", []))


# ── kb__list ──────────────────────────────────────────────────────

@router.get("/list")
async def list_kb_tools(
    query: Optional[str] = Query(None, min_length=1, max_length=200, description="大小写不敏感的名称/来源子串过滤"),
    groupId: Optional[str] = Query(None, min_length=1, description="按知识库分组筛选"),
    user: dict = Depends(get_current_user),
):
    """列出可用知识库及样本来源（kb__list 等价）

    返回每个知识库的名称、分组、项数，以及若干样本来源（文件名、URL、笔记标题等），
    供 AI 模型判断覆盖哪些主题。调用 kb__search 前建议先调此接口。
    """
    # 获取用户所有知识库
    bases_result = KnowledgeBaseService.list(user["id"], page=1, limit=1000)
    all_bases = bases_result.get("items", [])

    # 按 groupId 过滤
    if groupId is not None:
        all_bases = [b for b in all_bases if b.get("groupId") == groupId]

    # 构建输出项
    output_items = []
    for base in all_bases:
        root_items = []
        if base.get("status") == "completed":
            try:
                root_items = KnowledgeItemService.get_root_items_by_base_id(user["id"], base["id"])
            except Exception as e:
                logger.warning("获取根知识项失败: baseId=%s error=%s", base["id"], e)

        completed_items = [it for it in root_items if it.get("status") == "completed"]
        sample_sources = []
        for it in completed_items[:SAMPLE_LIMIT]:
            source = derive_sample_source(it)
            if source:
                sample_sources.append(source)

        output_items.append({
            "id": base["id"],
            "name": base.get("name", ""),
            "groupId": base.get("groupId"),
            "status": base.get("status", "completed"),
            "documentCount": base.get("documentCount", 0) or 0,
            "itemCount": len(root_items),
            "sampleSources": sample_sources,
        })

    # 按 query 子串过滤
    if query:
        lowered = query.lower()
        output_items = [item for item in output_items if matches_query(item, lowered)]

    return {"data": output_items, "message": "success", "code": 200}


# ── kb__search ────────────────────────────────────────────────────

class KbSearchInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=200, description="搜索关键词（2–200 字符）")
    baseIds: list[str] = Field(..., min_length=1, description="要搜索的知识库 ID 列表，至少一个")


async def _safe_search(orchestrator, user_id: int, base_id: str, query: str) -> list[dict]:
    """安全地搜索单个知识库，失败时返回空列表"""
    try:
        return await orchestrator.search(user_id, base_id, query)
    except Exception as e:
        logger.warning("知识库搜索失败: baseId=%s query=%s error=%s", base_id, query, e)
        return []


def _batch_get_item_sources(user_id: int, item_ids: list[str]) -> dict[str, str]:
    """批量查询知识项来源（按 item_id 查询，返回 id→source 映射）"""
    if not item_ids:
        return {}

    unique_ids = list(dict.fromkeys(item_ids))
    placeholders = ",".join("?" for _ in unique_ids)

    db = get_db()
    try:
        rows = db.execute(
            f"""SELECT ki.id, ki.type, ki.data
                FROM knowledge_items ki
                JOIN knowledge_bases kb ON kb.id = ki.base_id
                WHERE ki.id IN ({placeholders}) AND kb.user_id = ?""",
            [*unique_ids, user_id],
        ).fetchall()
    finally:
        db.close()

    sources = {}
    for row in rows:
        raw_data = row["data"]
        if isinstance(raw_data, str):
            try:
                data = json.loads(raw_data)
            except (json.JSONDecodeError, TypeError):
                data = {}
        elif isinstance(raw_data, dict):
            data = raw_data
        else:
            data = {}
        sources[row["id"]] = derive_source_from_item({"id": row["id"], "type": row["type"], "data": data})

    return sources


@router.post("/search")
async def search_kb_tools(
    body: KbSearchInput,
    user: dict = Depends(get_current_user),
):
    """搜索知识库（kb__search 等价）

    在指定知识库中搜索文本，返回去重并按分数降序排列的结果。
    每个结果包含内容、分数和来源信息。
    建议先调用 kb__list 查看可用知识库，再选 baseIds 来搜索。
    """
    query = body.query.strip()
    base_ids = body.baseIds

    # 并行搜索所有 baseId
    per_base_results = await asyncio.gather(
        *[_safe_search(knowledge_orchestration_service, user["id"], bid, query) for bid in base_ids],
    )

    # 合并结果
    merged = []
    for results in per_base_results:
        merged.extend(results)

    if not merged:
        return {"data": [], "message": "success", "code": 200}

    # 按 content（text）去重，保留最高分
    deduped: dict[str, dict] = {}
    for result in merged:
        content = result.get("text", "")
        score = result.get("score", 0)
        existing = deduped.get(content)
        if existing is None or score > existing.get("score", 0):
            deduped[content] = result

    # 排序（分数降序）
    sorted_results = sorted(deduped.values(), key=lambda r: r.get("score", 0), reverse=True)

    # 批量查询 item 来源
    all_item_ids = [r.get("item_id", "") for r in sorted_results if r.get("item_id")]
    item_sources = _batch_get_item_sources(user["id"], all_item_ids)

    # 构建输出
    output = []
    for idx, result in enumerate(sorted_results):
        content = result.get("text", "")
        score = max(0, min(1, result.get("score", 0)))
        item_id = result.get("item_id", "")
        source = item_sources.get(item_id, item_id)

        output.append({
            "id": idx + 1,
            "content": content,
            "score": score,
            "source": source,
        })

    return {"data": output, "message": "success", "code": 200}
