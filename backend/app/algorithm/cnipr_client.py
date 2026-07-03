"""
CNIPR 专利开放平台 API 客户端

使用 Password Grant 模式获取 access_token，支持自动刷新。
不存储专利数据到本地数据库，所有检索实时走 API。
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  API 端点
# ══════════════════════════════════════════════════════════

CNIPR_BASE = "https://open.cnipr.com"
AUTH_URL = f"{CNIPR_BASE}/oauth/json/user/login"
REFRESH_URL = f"{CNIPR_BASE}/oauth/json/user/refresh"
SEARCH_URL = f"{CNIPR_BASE}/cnipr-api/v1/api/search/sf1"
DOWNLOAD_URL = f"{CNIPR_BASE}/cnipr-api/v1/api/download/dl3"


# ══════════════════════════════════════════════════════════
#  Token 管理（内存缓存，自动刷新）
# ══════════════════════════════════════════════════════════

class TokenManager:
    """管理 CNIPR access_token / refresh_token，自动在过期前刷新。"""

    def __init__(self):
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._open_id: str = ""
        self._open_key: str = ""
        self._expires_at: float = 0  # Unix timestamp

    async def get_token(self) -> str:
        """获取有效的 access_token，过期前自动刷新。"""
        if time.time() < self._expires_at - 60:
            return self._access_token
        await self._refresh_or_login()
        return self._access_token

    async def get_open_id(self) -> str:
        if not self._open_id:
            await self._refresh_or_login()
        return self._open_id

    async def _refresh_or_login(self):
        """优先用 refresh_token，否则重新登录。"""
        if self._refresh_token:
            try:
                await self._do_refresh()
                return
            except Exception as e:
                logger.warning(f"CNIPR refresh_token 失败，重新登录: {e}")

        await self._do_login()

    async def _do_login(self):
        """Password Grant 登录获取 access_token。"""
        if not settings.CNIPR_CLIENT_ID or not settings.CNIPR_USERNAME:
            raise RuntimeError("CNIPR 配置不完整，缺少 CNIPR_CLIENT_ID 或 CNIPR_USERNAME")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(AUTH_URL, data={
                "user_account": settings.CNIPR_USERNAME,
                "user_password": settings.CNIPR_PASSWORD,
                "client_id": settings.CNIPR_CLIENT_ID,
                "client_secret": settings.CNIPR_CLIENT_SECRET,
                "grant_type": "password",
                "return_refresh_token": "1",
            })

        body = resp.json()
        if body.get("status") != 0:
            raise RuntimeError(f"CNIPR 登录失败: {body.get('message', body)}")

        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token", "")
        self._open_id = body.get("open_id", "")
        self._open_key = body.get("open_key", "")
        expires_in = body.get("expires_in", 2592000)  # 默认 30 天
        self._expires_at = time.time() + expires_in
        logger.info(f"CNIPR 登录成功，token 有效期 {expires_in // 86400} 天")

    async def _do_refresh(self):
        """用 refresh_token 刷新 access_token。"""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(REFRESH_URL, data={
                "refresh_token": self._refresh_token,
                "client_id": settings.CNIPR_CLIENT_ID,
                "client_secret": settings.CNIPR_CLIENT_SECRET,
                "grant_type": "refresh_token",
            })

        body = resp.json()
        if body.get("status") != 0:
            raise RuntimeError(f"CNIPR 刷新失败: {body.get('message', body)}")

        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token", self._refresh_token)
        expires_in = body.get("expires_in", 2592000)
        self._expires_at = time.time() + expires_in
        logger.info("CNIPR token 刷新成功")


# 全局单例
_token_manager = TokenManager()


# ══════════════════════════════════════════════════════════
#  专利检索 API
# ══════════════════════════════════════════════════════════

async def search_patents(
    exp: str,
    page: int = 1,
    page_size: int = 20,
    display_cols: str = (
        "pid,title,abs,pubNumber,appNumber,appDate,pubDate,"
        "applicantName,inventorName,mainIpc,ipc,patType,"
        "legalStatus,statusCode"
    ),
    order: str = "-appDate",
    dbs: str = "FMZL,FMSQ,SYXX",
) -> dict[str, Any]:
    """
    调用 sf1-v1 检索专利。

    Args:
        exp: 检索表达式，如 "名称=(电池安全) AND 主分类号=(H01M)"
        page: 页码（从 1 开始）
        page_size: 每页条数（1-50）
        display_cols: 返回字段列表（逗号分隔）
        order: 排序，+appDate 升序 / -appDate 降序
        dbs: 专利库，FMZL=发明授权, FMSQ=发明申请, SYXX=实用新型

    Returns:
        {"total": int, "results": list[dict], "from": int, "size": int}
    """
    token = await _token_manager.get_token()
    open_id = await _token_manager.get_open_id()

    client_id = settings.CNIPR_CLIENT_ID
    url = f"{SEARCH_URL}/{client_id}"

    from_idx = (page - 1) * page_size

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, data={
            "openid": open_id,
            "access_token": token,
            "exp": exp,
            "dbs": dbs,
            "option": "2",  # 按字检索
            "order": order,
            "from": str(from_idx),
            "size": str(min(page_size, 50)),
            "displayCols": display_cols,
            "pidSign": "1",
        })

    body = resp.json()

    if body.get("status") != 0:
        msg = body.get("message", str(body))
        logger.error(f"CNIPR 检索失败 (status={body.get('status')}): {msg}")
        return {"total": 0, "results": [], "message": msg}

    return {
        "total": body.get("total", 0),
        "results": body.get("results", []),
        "from": from_idx,
        "size": page_size,
        "sections": body.get("sectionInfos", []),
    }


async def get_patent_detail(pids: list[str]) -> list[dict]:
    """
    调用 dl3-v1 批量获取专利详情（权利要求书、说明书等）。

    Args:
        pids: 专利 ID 列表（sf1-v1 返回的 pid 字段）

    Returns:
        专利详情列表
    """
    if not pids:
        return []

    token = await _token_manager.get_token()
    open_id = await _token_manager.get_open_id()

    client_id = settings.CNIPR_CLIENT_ID
    url = f"{DOWNLOAD_URL}/{client_id}"

    # 构建表达式：用 OR 拼接 pid
    pid_exps = " OR ".join(f'公开(公告)号=\'{pid}\'' for pid in pids)
    # 实际上 dl3-v1 接受 pid_list
    pids_str = ",".join(pids)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, data={
            "openid": open_id,
            "access_token": token,
            "pids": pids_str,
            "pidSign": "1",
        })

    body = resp.json()

    if body.get("status") != 0:
        msg = body.get("message", str(body))
        logger.error(f"CNIPR 下载失败: {msg}")
        return []

    return body.get("results", [])


async def analyze_patents(
    exp: str,
    analysis_field: str,
    dbs: str = "FMZL,FMSQ,SYXX",
) -> dict:
    """
    调用 as1 单字段分析接口（统计图表数据）。

    Args:
        exp: 检索表达式
        analysis_field: 分析字段，如 mainIpcSection / applicantName / pubDate
    """
    token = await _token_manager.get_token()
    open_id = await _token_manager.get_open_id()

    client_id = settings.CNIPR_CLIENT_ID
    url = f"{CNIPR_BASE}/cnipr-api/v1/api/analysis/as1/{client_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, data={
            "openid": open_id,
            "access_token": token,
            "exp": exp,
            "dbs": dbs,
            "option": "2",
            "from": "0",
            "size": "50",
            "analysis": analysis_field,
        })

    body = resp.json()
    if body.get("status") != 0:
        logger.error(f"CNIPR 分析失败: {body.get('message', body)}")
        return {}

    return body
