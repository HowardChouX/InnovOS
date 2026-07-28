"""管理员用户管理 - 基于 ORM + FastAPI Users。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.instance import current_superuser
from app.db.models import User
from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["admin-users"])


class UpdateUserInput(BaseModel):
    is_active: bool | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None


@router.get("")
def list_users(
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """列出所有用户。"""
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return {
        "data": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "phone": u.phone,
                "role": u.role,
                "isActive": u.is_active,
                "isSuperuser": u.is_superuser,
                "isVerified": u.is_verified,
            }
            for u in users
        ],
        "message": "success",
        "code": 200,
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserInput,
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """更新用户。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="无效角色")
        user.role = body.role
    if body.email is not None:
        user.email = body.email
    if body.phone is not None:
        user.phone = body.phone

    db.commit()
    db.refresh(user)
    return {
        "data": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "phone": user.phone,
            "role": user.role,
            "isActive": user.is_active,
        },
        "message": "success",
        "code": 200,
    }


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """删除用户。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"data": None, "message": "已删除", "code": 200}


@router.post("/{user_id}/revoke-tokens")
def revoke_user_tokens(
    user_id: int,
    db: Session = Depends(get_session),
    _admin=Depends(current_superuser),
):
    """撤销用户所有 token（token_version + 1）。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.token_version += 1
    db.commit()
    return {"ok": True}