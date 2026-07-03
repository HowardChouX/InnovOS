"""
PatentHub API 客户端 — 主数据源
Token-based 认证，支持搜索、详情、权利要求、说明书。
免费版限制：50次搜索/天，无排序，无高级统计。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  API 端点
# ══════════════════════════════════════════════════════════

PATENTHUB_BASE = "https://www.patenthub.cn/api"
SEARCH_URL = f"{PATENTHUB_BASE}/s"
PATENT_BASE_URL = f"{PATENTHUB_BASE}/patent/base"
PATENT_CLAIMS_URL = f"{PATENTHUB_BASE}/patent/claims"
PATENT_DESC_URL = f"{PATENTHUB_BASE}/patent/desc"


def _get_token() -> str:
    """获取 PatentHub API Token"""
    token = getattr(settings, "PATENT_HUB_TOKEN", "")
    if not token:
        raise RuntimeError("PatentHub Token 未配置，请设置 PATENT_HUB_TOKEN 环境变量")
    return token


# ══════════════════════════════════════════════════════════
#  搜索接口
# ══════════════════════════════════════════════════════════

async def search_patents(
    q: str,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """
    PatentHub 专利搜索。

    搜索语法示例：
      q=title:石墨烯 AND ipc:H01M
      q=summary:电池热管理
      q=applicant:华为

    Args:
        q: 搜索表达式
        page: 页码（从 1 开始）
        page_size: 每页条数（1-50）

    Returns:
        {
            "total": int,
            "patents": list[dict],
            "page": int,
            "total_pages": int,
        }
    """
    if not q.strip():
        return {"total": 0, "patents": [], "page": page, "total_pages": 0}

    token = _get_token()

    params = {
        "t": token,
        "q": q.strip(),
        "p": page,
        "ps": min(page_size, 50),
        "v": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(SEARCH_URL, params=params)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"PatentHub 搜索请求失败: {e}")
        return {"total": 0, "patents": [], "page": page, "total_pages": 0, "error": str(e)}

    code = body.get("code", 0)
    if code != 200:
        msg = body.get("message", f"PatentHub 错误码: {code}")
        logger.warning(f"PatentHub 搜索失败 (code={code}): {msg}")
        return {"total": 0, "patents": [], "page": page, "total_pages": 0, "error": msg}

    patents_raw = body.get("patents", [])
    total = body.get("total", 0)
    total_pages = body.get("totalPages", 0)

    # 标准化专利数据格式
    patents = []
    for p in patents_raw:
        patents.append(_normalize_patent(p))

    return {
        "total": total,
        "patents": patents,
        "page": body.get("page", page),
        "total_pages": total_pages,
    }


# ══════════════════════════════════════════════════════════
#  专利详情接口
# ══════════════════════════════════════════════════════════

async def get_patent_base(patent_id: str) -> dict[str, Any] | None:
    """
    获取单个专利基本信息。

    Args:
        patent_id: 专利ID（如 CN111344253A）

    Returns:
        专利基本信息字典，失败返回 None
    """
    if not patent_id.strip():
        return None

    token = _get_token()

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                PATENT_BASE_URL,
                params={"t": token, "id": patent_id.strip(), "v": 1},
            )
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"PatentHub 获取专利详情失败(id={patent_id}): {e}")
        return None

    if body.get("code") != 200:
        logger.warning(f"PatentHub 专利详情失败(id={patent_id}): code={body.get('code')}")
        return None

    return body.get("patent") or body.get("data")


async def get_patent_claims(patent_id: str) -> str:
    """
    获取专利权利要求书全文。

    Args:
        patent_id: 专利ID

    Returns:
        权利要求书文本，失败返回空字符串
    """
    if not patent_id.strip():
        return ""

    token = _get_token()

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                PATENT_CLAIMS_URL,
                params={"t": token, "id": patent_id.strip(), "v": 1},
            )
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"PatentHub 获取权利要求失败(id={patent_id}): {e}")
        return ""

    if body.get("code") != 200:
        return ""

    # 权利要求可能在 data 或 claims 字段
    return body.get("data") or body.get("claims") or ""


async def get_patent_description(patent_id: str) -> str:
    """
    获取专利说明书全文。

    Args:
        patent_id: 专利ID

    Returns:
        说明书文本，失败返回空字符串
    """
    if not patent_id.strip():
        return ""

    token = _get_token()

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                PATENT_DESC_URL,
                params={"t": token, "id": patent_id.strip(), "v": 1},
            )
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"PatentHub 获取说明书失败(id={patent_id}): {e}")
        return ""

    if body.get("code") != 200:
        return ""

    return body.get("data") or body.get("description") or ""


# ══════════════════════════════════════════════════════════
#  批量获取详情（降级策略）
# ══════════════════════════════════════════════════════════

async def get_patent_full(patent_id: str) -> dict[str, Any] | None:
    """
    组合获取专利完整信息：base + claims + description。
    用于替代受限的 /api/patent/detail 接口。

    Args:
        patent_id: 专利ID

    Returns:
        包含完整信息的专利字典，失败返回 None
    """
    base = await get_patent_base(patent_id)
    if not base:
        return None

    # 并发获取 claims 和 description
    import asyncio
    claims_task = asyncio.create_task(get_patent_claims(patent_id))
    desc_task = asyncio.create_task(get_patent_description(patent_id))

    claims, description = await asyncio.gather(claims_task, desc_task)

    base["claims"] = claims
    base["description"] = description
    return base


# ══════════════════════════════════════════════════════════
#  数据标准化
# ══════════════════════════════════════════════════════════

def _normalize_patent(raw: dict) -> dict:
    """
    将 PatentHub 返回的原始专利数据标准化为统一格式。
    与 CNIPR 和本地数据库格式兼容。
    """
    return {
        "id": raw.get("id", ""),
        "title": raw.get("title", ""),
        "summary": raw.get("summary", raw.get("abstract", "")),
        "applicant": raw.get("applicant", raw.get("applicantName", "")),
        "inventor": raw.get("inventor", raw.get("inventorName", "")),
        "applicationDate": raw.get("applicationDate", raw.get("appDate", "")),
        "documentDate": raw.get("documentDate", raw.get("pubDate", "")),
        "mainIpc": raw.get("mainIpc", ""),
        "ipc": raw.get("ipc", raw.get("mainIpc", "")),
        "legalStatus": raw.get("legalStatus", ""),
        "type": raw.get("type", raw.get("patType", "")),
        "documentNumber": raw.get("documentNumber", raw.get("pubNumber", "")),
        "source": "patenthub",
    }
