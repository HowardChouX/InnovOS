"""管理员用户管理 — 走现有 psycopg2 路径，与模块其它部分保持一致。

ORM 仅在 FastAPI Users 内部使用（注册/登录/密码重置流程），后台管理侧
继续使用 db_session 以复用 MockDB 风格的测试桩。
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import SuperUserDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["admin-users"])


class UpdateUserInput(BaseModel):
    is_active: bool | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None


@router.get("")
def list_users(_admin=SuperUserDep):
    """列出所有用户。"""
    from app.database import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, email, username, phone, role, is_active, is_superuser, is_verified, token_version "
            "FROM users ORDER BY id"
        ).fetchall()
        return {
            "data": [
                {
                    "id": r["id"],
                    "email": r.get("email") or "",
                    "username": r.get("username") or "",
                    "phone": r.get("phone") or "",
                    "role": r.get("role") or "user",
                    "isActive": bool(r.get("is_active", 0)),
                    "isSuperuser": bool(r.get("is_superuser", 0)),
                    "isVerified": bool(r.get("is_verified", 0)),
                }
                for r in rows
            ],
            "message": "success",
            "code": 200,
        }
    finally:
        db.close()


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserInput,
    _admin=SuperUserDep,
):
    """更新用户。"""
    from app.database import get_db

    db = get_db()
    try:
        existing = db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="用户不存在")

        if body.role is not None and body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="无效角色")

        sets: list[str] = []
        params: list = []
        if body.is_active is not None:
            sets.append("is_active=?"); params.append(1 if body.is_active else 0)
        if body.role is not None:
            sets.append("role=?"); params.append(body.role)
        if body.email is not None:
            sets.append("email=?"); params.append(body.email)
        if body.phone is not None:
            sets.append("phone=?"); params.append(body.phone)
        if sets:
            params.append(user_id)
            db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", tuple(params))
            db.commit()

        row = db.execute(
            "SELECT id, email, username, phone, role, is_active FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        return {
            "data": {
                "id": row["id"],
                "email": row.get("email") or "",
                "username": row.get("username") or "",
                "phone": row.get("phone") or "",
                "role": row.get("role") or "user",
                "isActive": bool(row.get("is_active", 0)),
            },
            "message": "success",
            "code": 200,
        }
    finally:
        db.close()


@router.delete("/{user_id}")
def delete_user(user_id: int, _admin=SuperUserDep):
    """删除用户。禁止删除自己（包括 id=0 的根管理员与当前登录用户）。"""
    from app.database import get_db

    if user_id == 0:
        raise HTTPException(status_code=400, detail="不能删除根管理员")
    if _admin and getattr(_admin, "id", None) == user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    db = get_db()
    try:
        existing = db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="用户不存在")
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
        db.commit()
        return {"data": None, "message": "已删除", "code": 200}
    finally:
        db.close()


@router.post("/{user_id}/revoke-tokens")
def revoke_user_tokens(user_id: int, _admin=SuperUserDep):
    """撤销用户所有 token（token_version + 1）。"""
    from app.database import get_db

    db = get_db()
    try:
        existing = db.execute("SELECT token_version FROM users WHERE id=?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="用户不存在")
        new_ver = (existing["token_version"] or 0) + 1
        db.execute(
            "UPDATE users SET token_version=? WHERE id=?",
            (new_ver, user_id),
        )
        db.commit()
        return {"ok": True}
    finally:
        db.close()
