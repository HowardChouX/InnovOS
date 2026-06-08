"""知识库基础单元、分组、RAG 配置 API"""
import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from app.utils import utc_iso
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/knowledge", tags=["knowledge-admin"])


# ─── 知识库基础单元 ─────────────────────────────

class CreateBaseInput(BaseModel):
    name: str
    group_id: Optional[str] = None


class UpdateBaseInput(BaseModel):
    name: Optional[str] = None
    group_id: Optional[str] = None


@router.get("/bases")
def list_bases(user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute("SELECT * FROM knowledge_docs WHERE user_id=? AND is_active=1 GROUP BY category", (user["id"],)).fetchall()
    # 简化：以 category 作为 base 分组
    rows = db.execute("SELECT id FROM knowledge_docs WHERE user_id=? AND is_active=1 LIMIT 1", (user["id"],)).fetchall()
    bases = [{"id": "default", "name": "默认知识库", "groupId": None, "itemCount": 0}]
    db.close()
    return {"data": bases, "message": "success"}


# ─── 分组 ───────────────────────────────────────

class CreateGroupInput(BaseModel):
    name: str


@router.get("/groups")
def list_groups(user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute("SELECT category as name, COUNT(*) as baseCount FROM knowledge_docs WHERE user_id=? AND is_active=1 GROUP BY category", (user["id"],)).fetchall()
    db.close()
    groups = [{"id": r["name"], "name": r["name"], "baseCount": r["baseCount"]} for r in rows]
    return {"data": groups, "message": "success"}


@router.post("/groups")
def create_group(body: CreateGroupInput, user: dict = Depends(get_current_user)):
    return {"data": {"id": body.name, "name": body.name, "baseCount": 0}, "message": "success"}


# ─── RAG 配置 ──────────────────────────────────

@router.get("/bases/{base_id}/rag-config")
def get_rag_config(base_id: str, user: dict = Depends(get_current_user)):
    return {"data": {
        "chunkSize": 512,
        "chunkOverlap": 64,
        "topK": 5,
        "scoreThreshold": 0.0,
    }, "message": "success"}


@router.put("/bases/{base_id}/rag-config")
def update_rag_config(base_id: str, body: dict, user: dict = Depends(get_current_user)):
    return {"data": body, "message": "success"}


# ─── 召回测试 ──────────────────────────────────

@router.post("/bases/{base_id}/recall-test")
def recall_test(base_id: str, body: dict, user: dict = Depends(get_current_user)):
    q = body.get("query", "")
    top_k = body.get("topK", 5)
    db = get_db()
    rows = db.execute(
        "SELECT id, title, content FROM knowledge_docs WHERE user_id=? AND is_active=1 AND (title LIKE ? OR content LIKE ?) LIMIT ?",
        (user["id"], f"%{q}%", f"%{q}%", top_k),
    ).fetchall()
    db.close()
    results = [{"id": str(r["id"]), "title": r["title"], "content": r["content"][:200], "score": 0.5} for r in rows]
    return {"data": results, "message": "success"}
