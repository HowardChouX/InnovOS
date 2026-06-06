from openai import OpenAI
from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_admin
from app.algorithm.key_manager import key_manager
from app.algorithm.ai_client import pick_model
from app.algorithm.crypto import decrypt_key
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/keys", tags=["keys"])


class CreateKeyInput(BaseModel):
    key_name: str = Field(alias="keyName")
    api_key: str = Field(alias="apiKey")
    api_base_url: str = Field(default="https://api.deepseek.com", alias="apiBaseUrl")
    api_model: str = Field(default="", alias="apiModel")
    priority: int = Field(default=0)
    max_rpm: int = Field(default=60, alias="maxRpm")


class UpdateKeyInput(BaseModel):
    key_name: Optional[str] = Field(default=None, alias="keyName")
    api_key: Optional[str] = Field(default=None, alias="apiKey")
    api_base_url: Optional[str] = Field(default=None, alias="apiBaseUrl")
    api_model: Optional[str] = Field(default=None, alias="apiModel")
    is_active: Optional[bool] = Field(default=None, alias="isActive")
    priority: Optional[int] = Field(default=None)
    max_rpm: Optional[int] = Field(default=None, alias="maxRpm")


def row_to_dict(row: dict) -> dict:
    # 解密后取前缀脱敏，不暴露加密格式
    try:
        plain_key = decrypt_key(row["api_key"])
        masked = plain_key[:7] + "****" if len(plain_key) > 7 else "****"
    except Exception:
        masked = "****"
    return {
        "id": row["id"],
        "keyName": row["key_name"],
        "apiKey": masked,
        "apiBaseUrl": row["api_base_url"],
        "apiModel": row["api_model"],
        "isActive": bool(row["is_active"]),
        "priority": row["priority"],
        "maxRpm": row["max_rpm"],
        "currentRpm": row["current_rpm"],
        "requestCount": row["request_count"],
        "lastUsedAt": row.get("last_used_at"),
        "createdAt": row["created_at"],
    }


@router.get("")
def list_keys(user: dict = Depends(require_admin)):
    """获取API Key列表（仅管理员）"""
    keys = key_manager.list_keys()
    return {"data": [row_to_dict(k) for k in keys], "message": "success"}


@router.post("")
def create_key(body: CreateKeyInput, user: dict = Depends(require_admin)):
    """创建API Key（仅管理员）"""
    key = key_manager.create_key(
        key_name=body.key_name,
        api_key=body.api_key,
        api_base_url=body.api_base_url,
        api_model=body.api_model,
        priority=body.priority,
        max_rpm=body.max_rpm,
    )
    return {"data": row_to_dict(key), "message": "创建成功"}


@router.get("/{key_id}")
def get_key(key_id: int, user: dict = Depends(require_admin)):
    """获取单个Key（仅管理员）"""
    key = key_manager.get_key_by_id(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key不存在")
    return {"data": row_to_dict(key), "message": "success"}


@router.put("/{key_id}")
def update_key(key_id: int, body: UpdateKeyInput, user: dict = Depends(require_admin)):
    """更新API Key（仅管理员）"""
    updates = {}
    if body.key_name is not None:
        updates["key_name"] = body.key_name
    if body.api_key is not None:
        updates["api_key"] = body.api_key
    if body.api_base_url is not None:
        updates["api_base_url"] = body.api_base_url
    if body.api_model is not None:
        updates["api_model"] = body.api_model
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.priority is not None:
        updates["priority"] = body.priority
    if body.max_rpm is not None:
        updates["max_rpm"] = body.max_rpm

    key = key_manager.update_key(key_id, **updates)
    if not key:
        raise HTTPException(status_code=404, detail="Key不存在")
    return {"data": row_to_dict(key), "message": "更新成功"}


@router.delete("/{key_id}")
def delete_key(key_id: int, user: dict = Depends(require_admin)):
    """删除API Key（仅管理员）"""
    key_manager.delete_key(key_id)
    return {"message": "删除成功"}


@router.post("/{key_id}/test")
def test_key(key_id: int, user: dict = Depends(require_admin)):
    """测试API Key连接（仅管理员）"""
    key = key_manager.get_key_by_id(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key不存在")

    try:
        client = OpenAI(api_key=key["api_key"], base_url=key["api_base_url"])
        resp = client.chat.completions.create(
            model=pick_model(key["api_model"]),
            messages=[{"role": "user", "content": "回复'连接成功'"}],
            max_tokens=10
        )
        return {"message": "测试成功", "response": resp.choices[0].message.content}
    except Exception as e:
        return {"message": f"测试失败: {str(e)}"}
