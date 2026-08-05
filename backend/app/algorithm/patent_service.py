"""
专利检索服务 — 纯本地数据库

专利搜索与详情均从本地 PostgreSQL patents 表检索，
不再对接任何外部专利 API。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.database import db_session

logger = logging.getLogger(__name__)

# 常见泛化词/停用词，不作为检索词
_STOP_WORDS = {
    "方法",
    "装置",
    "系统",
    "结构",
    "模块",
    "单元",
    "设备",
    "一种",
    "一个",
    "该",
    "其",
    "的",
    "了",
    "基于",
    "根据",
    "用于",
    "利用",
    "采用",
    "使用",
    "进行",
    "通过",
    "包括",
    "设置",
    "提供",
    "实现",
    "发明",
    "本",
    "新型",
    "型",
    "方案",
    "技术",
    "问题",
    "这是",
    "可以",
    "以及",
    "或者",
    "如果",
    "对于",
    "相关",
    "研究",
}


def extract_keywords(text: str, max_keywords: int = 5) -> list[str]:
    """从文本中提取检索关键词（jieba 分词、去重、过滤停用词与过短词元）。"""
    if not text or not text.strip():
        return []
    import jieba

    keywords: list[str] = []
    seen: set[str] = set()
    for token in jieba.cut(text.strip()):
        token = token.strip(" \t,.;:、，。；！？!?\"'“”‘’")
        lowered = token.lower()
        if len(token) < 2 or lowered in seen or lowered in _STOP_WORDS:
            continue
        if not re.search(r"[a-zA-Z0-9一-鿿]", token):
            continue
        seen.add(lowered)
        keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


# ══════════════════════════════════════════════════════════
#  行 → 字典映射（服务层统一负责，API 与工作流共用）
# ══════════════════════════════════════════════════════════


def _parse_list_field(value: Any) -> list:
    """applicants/inventors/ipc_codes 在库中为 JSON 字符串，统一解析。"""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except (ValueError, TypeError):
            return [value]
    return []


def row_to_patent_dict(row: Any, relevance: float | int | None = None) -> dict:
    """将 patents 表行转为前端期望的字典格式。"""
    applicants = _parse_list_field(row["applicants"])
    inventors = _parse_list_field(row["inventors"])
    ipc_codes = _parse_list_field(row["ipc_codes"])
    score = relevance if relevance is not None else (row["relevance_score"] or 0)
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "summary": row["abstract"] or "",
        "abstract": row["abstract"] or "",
        "applicant": ", ".join(applicants),
        "inventor": ", ".join(inventors),
        "applicants": applicants,
        "inventors": inventors,
        "mainIpc": ipc_codes[0] if ipc_codes else "",
        "ipc": ", ".join(ipc_codes),
        "ipcCodes": ipc_codes,
        "legalStatus": "",
        "type": "",
        "documentNumber": row["patent_number"] or "",
        "patentNumber": row["patent_number"] or "",
        "patent_number": row["patent_number"] or "",
        "relevance_score": score,
        "relevance": score,
        "relevanceScore": score,
        "filingDate": row["filing_date"] or "",
        "filing_date": row["filing_date"] or "",
        "publicationDate": row["publication_date"] or "",
        "publication_date": row["publication_date"] or "",
        "applicationDate": row["filing_date"] or "",
        "documentDate": row["publication_date"] or "",
    }


# ══════════════════════════════════════════════════════════
#  工作流专利检索（纯本地）
# ══════════════════════════════════════════════════════════


def patent_search(
    innovations: list[dict],
    task_description: str = "",
    max_results: int = 50,
) -> dict[str, Any]:
    """
    工作流专利检索：仅查询本地数据库。

    按创新方向提取关键词检索本地专利库，并按方向分组、跨方向去重；
    无创新方向时用任务描述兜底。无匹配结果时返回空结果，工作流继续。

    Returns:
        {
            "patents": list[dict],          # 专利列表（含 relevance_score、source_innovation）
            "direction_patents": dict,      # 创新方向 → 专利标题映射
            "total_found": int,
        }
    """
    patents: list[dict] = []
    direction_patents: dict[str, list[str]] = {}
    seen_ids: set[str] = set()

    # (方向名, 检索文本)；方向名为空表示任务描述兜底
    sources: list[tuple[str, str]] = []
    for inn in innovations or []:
        desc = (inn.get("description") or "").strip()
        if desc:
            sources.append((desc, desc))
    if not sources:
        text = (task_description or "").strip()
        if text:
            sources.append(("", text))

    for direction, text in sources:
        if len(patents) >= max_results:
            break
        keywords = extract_keywords(text)
        if not keywords:
            continue
        rows = _search_rows_by_keywords(keywords, limit=max_results - len(patents))
        for row in rows:
            pid = str(row["id"])
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            patent = row_to_patent_dict(row, relevance=_keyword_relevance(row, keywords))
            patent["source_innovation"] = direction
            patents.append(patent)
            if direction:
                direction_patents.setdefault(direction, []).append(patent["title"])

    patents.sort(key=lambda p: p["relevance_score"], reverse=True)
    return {
        "patents": patents,
        "direction_patents": direction_patents,
        "total_found": len(patents),
    }


def _search_rows_by_keywords(keywords: list[str], limit: int) -> list:
    """按关键词检索本地专利（title/abstract 模糊匹配，参数化查询）。"""
    conditions = " OR ".join("(title LIKE ? OR abstract LIKE ?)" for _ in keywords)
    params: list[Any] = []
    for kw in keywords:
        like = f"%{kw}%"
        params.extend([like, like])
    sql = f"SELECT * FROM patents WHERE {conditions} ORDER BY relevance_score DESC, id LIMIT ?"
    with db_session() as db:
        return db.execute(sql, [*params, limit]).fetchall()


def _keyword_relevance(row: Any, keywords: list[str]) -> int:
    """以关键词命中率作为相关度（0-100），用于结果排序。"""
    if not keywords:
        return 0
    text = f"{row['title'] or ''} {row['abstract'] or ''}".lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return round(hits * 100 / len(keywords))


# ══════════════════════════════════════════════════════════
#  专利详情（纯本地）
# ══════════════════════════════════════════════════════════


def get_patent_detail(pid: str) -> dict[str, Any] | None:
    """
    获取专利详情（仅本地数据库）。

    依次按 内部 ID → 专利号 → 公开号 查找；未找到返回 None。
    """
    pid = (pid or "").strip()
    if not pid:
        return None

    with db_session() as db:
        row = None
        if pid.isdigit():
            row = db.execute("SELECT * FROM patents WHERE id = ?", [int(pid)]).fetchone()
        if not row:
            row = db.execute("SELECT * FROM patents WHERE patent_number = ?", [pid]).fetchone()
        if not row:
            row = db.execute("SELECT * FROM patents WHERE publication_number = ?", [pid]).fetchone()

    if not row:
        return None

    patent = row_to_patent_dict(row)
    patent["claims"] = row["claims"] or ""
    patent["description"] = row["description"] or ""
    return patent
