"""InnovOS 扩展：用户自助修改密码。

FastAPI Users 的 users router 已经覆盖了 GET /api/users/me 与 PATCH /api/users/me，
但没有提供「校验旧密码 + 更新新密码」的流程。本路由补齐该能力。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.instance import current_active_user
from app.auth.users import get_user_manager
from app.db.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


class ChangePasswordInput(BaseModel):
    """PUT /api/users/me/password"""

    current_password: str
    new_password: str = Field(min_length=8)


@router.put("/me/password")
async def change_password(
    body: ChangePasswordInput,
    user: User = Depends(current_active_user),
    user_manager=Depends(get_user_manager),
) -> dict:
    """用户自助修改密码：校验旧密码 → 哈希新密码 → 持久化。"""
    valid, _ = user_manager.password_helper.verify_and_update(
        body.current_password, user.hashed_password
    )
    if not valid:
        raise HTTPException(status_code=400, detail="当前密码错误")

    try:
        await user_manager.validate_password(body.new_password, user)
    except Exception as exc:  # InvalidPasswordException
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_hash = user_manager.password_helper.hash(body.new_password)
    user.hashed_password = new_hash
    # 修改密码同时递增 token_version，使旧 token 全部失效
    user.token_version = (user.token_version or 0) + 1
    await user_manager.update(user, {"hashed_password": new_hash, "token_version": user.token_version})
    return {"message": "密码已修改"}
