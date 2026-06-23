"""
Auth API routes — raw psycopg2 (SQLModel removed).

管理员：每次登录从 .env 验证，不存 DB。
普通用户：通过 psycopg2 raw SQL 注册/登录验证。
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.deps import CurrentUser, SessionDep
from app.audit import log_audit
from app.auth import (
    _verify_admin_credentials,
    clear_token_cookie,
    create_access_token,
    set_token_cookie,
)
from app.crud.users import create_user, get_user_by_username
from app.models.user import UserLogin, UserPublic, UserRegister

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(
    body: UserRegister,
    db: SessionDep,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Register a new regular user.

    Returns access_token + user data (consistent with login response).
    """
    existing = get_user_by_username(db=db, username=body.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = create_user(db=db, user_in=body)

    uid: int = user.id  # type: ignore[assignment]  # guaranteed non-None after commit
    log_audit(
        uid,
        user.username,
        "user.register",
        "user",
        str(uid),
        {},
        request.client.host if request.client else "",
    )

    token = create_access_token({"user_id": uid, "role": user.role, "token_version": user.token_version})
    set_token_cookie(response, token)
    return {
        "access_token": token,
        "user": UserPublic(
            id=uid,
            username=user.username,
            email=user.email or "",
            role=user.role,
            created_at=user.created_at,
        ).model_dump(),
    }


@router.post("/login")
def login(
    body: UserLogin,
    db: SessionDep,
    request: Request,
    response: Response,
) -> Any:
    """Login — supports admin (env-based) and regular users."""
    username = body.username.strip()
    password = body.password

    # 优先验证管理员：从 .env 实时校验，不经过数据库
    if _verify_admin_credentials(username, password):
        token = create_access_token(
            {
                "user_id": 0,
                "role": "admin",
                "username": username,
                "token_version": 0,
            }
        )
        set_token_cookie(response, token)
        log_audit(
            0,
            username,
            "user.login",
            "admin",
            "env",
            {},
            request.client.host if request.client else "",
        )
        return {
            "access_token": token,
            "user": {"id": 0, "username": username, "role": "admin", "email": "", "created_at": ""},
        }

    # 普通用户：通过 psycopg2 raw SQL 验证
    from app.crud.users import authenticate

    user = authenticate(db=db, username=username, password=password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    uid: int = user.id  # type: ignore[assignment]  # guaranteed non-None after commit
    log_audit(
        uid,
        user.username,
        "user.login",
        "user",
        str(uid),
        {},
        request.client.host if request.client else "",
    )

    token = create_access_token({"user_id": uid, "role": user.role, "token_version": user.token_version})
    set_token_cookie(response, token)
    return {
        "access_token": token,
        "user": UserPublic(
            id=uid,
            username=user.username,
            email=user.email or "",
            role=user.role,
            created_at=user.created_at,
        ).model_dump(),
    }


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Clear auth cookie."""
    clear_token_cookie(response)
    return {"message": "已退出登录"}


@router.get("/me", response_model=UserPublic)
def me(current_user: CurrentUser) -> Any:
    """Return the currently authenticated user."""
    return current_user
