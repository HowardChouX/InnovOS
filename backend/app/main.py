"""
FastAPI application entry point.

The `app` package import triggers bootstrap (load_dotenv + setup_logging)
via its __init__.py. All subsequent imports are E402-clean.
"""

import asyncio
import logging
import os
import shutil
import time
from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Importing any app submodule triggers app/__init__.py bootstrap (load_dotenv + setup_logging)
from app.api import analysis, evaluation, feedback, modeling, notifications, patents, solutions, tasks, workflow
from app.api import conversion as conversion_api
from app.api import kb_tools as kb_tools_api
from app.api import knowledge as knowledge_api
from app.api import knowledge_bases as knowledge_bases_api
from app.api import models as models_api
from app.api import profile as profile_api
from app.api.admin import router as admin_router
from app.api.sidebar import router as sidebar_router
from app.api.workflow_steps import router as workflow_steps_router
from app.core.config import settings
from app.database import _pg_pool, get_db
from app.middleware import (
    GlobalExceptionHandler,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.rate_limit_redis import api_limiter, auth_limiter, get_client_ip, register_limiter

logger = logging.getLogger(__name__)

# ── FastAPI app ──────────────────────────────────────────────
app_ = FastAPI(title="InnovOS API", description="创新智能平台后端 API")  # noqa: F811

# ── 中间件注册顺序（外层→内层） ──────────────────────────
# 请求先经过: RequestID → Logging → SecurityHeaders → CORS → GlobalException → router
# 响应反向经过所有中间件
app_.add_middleware(GlobalExceptionHandler)  # 最外层兜底
app_.add_middleware(RequestLoggingMiddleware)
app_.add_middleware(SecurityHeadersMiddleware)
app_.add_middleware(RequestIDMiddleware)  # 最先执行（生成 request_id）

# CORS — 开发环境允许前端调试地址，生产环境无回退
_dev_origins: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"]
if settings.ENVIRONMENT == "production":
    cors_origins = settings.all_cors_origins or []
else:
    cors_origins = settings.all_cors_origins or _dev_origins
app_.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)


# ── 限流中间件（独立实现，路由级） ──────────────────────
@app_.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 对敏感路由启用限流
    # Normalize path to prevent trailing-slash bypass
    path = request.url.path.rstrip("/") or "/"
    ip = get_client_ip(request)

    if path == "/api/auth/jwt/login":
        allowed, remaining, reset = auth_limiter.check(ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(reset)},
                content={"detail": "登录请求过于频繁，请稍后再试", "retryAfter": reset},
            )
    elif path == "/api/auth/register":
        allowed, remaining, reset = register_limiter.check(ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(reset)},
                content={"detail": "注册请求过于频繁，请稍后再试", "retryAfter": reset},
            )
    elif path.startswith("/api/") and path != "/api/health":
        allowed, remaining, reset = api_limiter.check(ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(reset)},
                content={"detail": "请求过于频繁，请稍后再试", "retryAfter": reset},
            )

    response = await call_next(request)
    return response


@app_.on_event("startup")
async def startup():
    """启动时初始化数据库、初始化模型注册表、知识库作业系统 + 专利向量表"""
    # 1. 应用 Alembic 迁移（DDL 真源；包括 users 表的 FastAPI Users 字段）
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        # 强制用当前 settings 的 DATABASE_URL 覆盖 alembic.ini 里的空值
        from app.core.config import settings
        if settings.DATABASE_URL:
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        await asyncio.to_thread(command.upgrade, alembic_cfg, "heads")
        logger.info("Alembic 迁移已应用至 head")
    except Exception as e:
        logger.error(f"Alembic 迁移失败: {e}")
        raise

    # 2. 初始化数据库表（非 users 表的 DDL 兜底；向后兼容老部署）
    try:
        from app.database import init_db

        await asyncio.to_thread(init_db)
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

    # 2. 加载模型注册表
    from app.algorithm.model_registry import model_registry

    await asyncio.to_thread(model_registry.load)
    logger.info("模型注册表已加载")

    # 3. 注入首任超级用户（仅当 .env 提供 FIRST_SUPERUSER 时执行；幂等）
    try:
        from app.auth.seed import seed_first_superuser_if_configured

        await asyncio.to_thread(seed_first_superuser_if_configured)
    except Exception as e:
        logger.warning(f"首任超级用户种子失败（非致命）: {e}")

    # 4. ~~ 自动种子化有环境变量 API Key 的内置供应商 ~~
    # 已废弃:环境变量不再承载 API Key,所有 Provider / Key 由管理员通过
    # /admin/model-providers 页面录入数据库。管理员登录后手动添加。

    # 4.5 初始化知识库作业系统
    from app.services.knowledge_orchestration_service import knowledge_orchestration_service

    await knowledge_orchestration_service.start()
    logger.info("知识库作业系统已启动")

    # 5. 启动自动快照备份服务
    from app.services.backup_service import backup_service

    await backup_service.start()

    # 5.1 种子化 Mock 数据（手机发热主题：专利/笔记/历史方案）
    try:
        from app.seed_mock_data import seed_all_mock_data

        await asyncio.to_thread(seed_all_mock_data)
        logger.info("Mock 种子数据已就绪")
    except Exception as e:
        logger.warning(f"Mock 种子数据初始化失败（非致命）: {e}")

    # 6. 建专利向量表并重建所有向量
    try:
        from app.algorithm.patent_search_engine import get_patent_search_engine, init_patent_vectors_table

        init_patent_vectors_table()
        engine = get_patent_search_engine()
        if engine.embedder:
            db = get_db()
            db.execute("DELETE FROM patent_vectors")
            db.commit()
            count = await engine.backfill()
            logger.info("Patent vectors rebuilt", extra={"count": count})
            # 创建 HNSW 索引（halfvec 支持 ≤4000 维）
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_patent_embedding_hnsw
                ON patent_vectors USING hnsw (embedding halfvec_cosine_ops)
                WITH (m = 16, ef_construction = 200)
            """)
            db.commit()
            logger.info("HNSW index created")
            db.close()
    except Exception as e:
        logger.warning(f"Patent vector init failed (non-fatal): {e}")


@app_.on_event("shutdown")
async def shutdown():
    """优雅关闭：释放连接池、取消后台任务。"""
    logger.info("Shutting down InnovOS API...")
    global _pg_pool
    if _pg_pool is not None:
        try:
            _pg_pool.closeall()
            logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            logger.warning("Error closing PG pool: %s", e)
    # 停止自动快照备份服务
    from app.services.backup_service import backup_service

    await backup_service.stop()

    # 取消所有后台任务
    pending_tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in pending_tasks:
        t.cancel()
    logger.info("Shutdown complete")


# ── FastAPI Users 路由 ──────────────────────────────────
from app.api.auth_login import router as auth_login_router
from app.api.auth_register import router as auth_register_router
from app.api.email_verification import router as email_verification_router
from app.api.password_reset import router as password_reset_router
from app.api.phone_verification import router as phone_verification_router
from app.auth.backend import auth_backend
from app.auth.exceptions import fastapi_users_exception_handler
from app.auth.instance import fastapi_users
from app.auth.schemas import UserRead, UserUpdate
from app.exceptions.email_verification import (
    EmailVerificationError,
    email_verification_exception_handler,
)
from app.exceptions.sms_verification import (
    SmsVerificationError,
    sms_verification_exception_handler,
)
from fastapi_users.exceptions import (
    InvalidPasswordException,
    InvalidResetPasswordToken,
    UserAlreadyExists,
    UserNotExists,
)

app_.include_router(
    fastapi_users.get_auth_router(auth_backend, requires_verification=True),
    prefix="/api/auth/jwt", tags=["auth"],
)
# 自定义注册路由（phone 必填 + 短信自动下发）替代 fastapi_users 默认注册端点
app_.include_router(auth_register_router)
# 自定义验证码登录路由（phone + SMS code）
app_.include_router(auth_login_router)
# 短信验证码发送/核验端点（发送 OTP + 注册验证翻 is_verified）
app_.include_router(phone_verification_router)
# 保留 fastapi-users 内置重置密码路由（向后兼容，前端走自研 /password-reset/*）
app_.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/api/auth", tags=["auth"],
)
# 移除 fastapi_users.get_verify_router(UserRead) -- 改用自实现 /email-verifications
app_.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate, requires_verification=True),
    prefix="/api/users", tags=["users"],
)
app_.include_router(email_verification_router)
app_.include_router(password_reset_router)
app_.add_exception_handler(EmailVerificationError, email_verification_exception_handler)
app_.add_exception_handler(SmsVerificationError, sms_verification_exception_handler)
for exc in (
    UserAlreadyExists, UserNotExists,
    InvalidResetPasswordToken, InvalidPasswordException,
):
    app_.add_exception_handler(exc, fastapi_users_exception_handler)

app_.include_router(tasks.router)
app_.include_router(analysis.router)
app_.include_router(patents.router)
app_.include_router(solutions.router)
app_.include_router(workflow.router)
app_.include_router(evaluation.router)
app_.include_router(feedback.router)
app_.include_router(admin_router)
app_.include_router(notifications.router)
app_.include_router(sidebar_router)
app_.include_router(knowledge_api.router)
app_.include_router(knowledge_bases_api.router)
app_.include_router(kb_tools_api.router)
app_.include_router(models_api.router)
app_.include_router(modeling.router)
app_.include_router(profile_api.router)
app_.include_router(conversion_api.router)
app_.include_router(workflow_steps_router)


@app_.get("/api/health")
def health_check():
    checks = {}
    overall = "healthy"

    # Database check
    try:
        db = get_db()
        start = time.time()
        db.execute("SELECT 1").fetchone()
        db_time = round((time.time() - start) * 1000, 1)
        db.close()
        checks["database"] = {"status": "ok", "responseMs": db_time}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
        overall = "degraded"

    # Disk space check (PostgreSQL data volume)
    try:
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        disk = shutil.disk_usage(cwd)
        used_pct = round(disk.used / disk.total * 100, 1)
        free_gb = round(disk.free / (1024**3), 2)
        status = "ok" if used_pct < 90 else "warning" if used_pct < 95 else "error"
        checks["disk"] = {"status": status, "usedPercent": used_pct, "freeGB": free_gb}
        if status == "error":
            overall = "degraded"
    except Exception as e:
        checks["disk"] = {"status": "error", "message": str(e)}

    # Memory check (reads /proc/meminfo, no external dependencies)
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:"):
                    mem[parts[0].rstrip(":")] = int(parts[1])
        total_kb = mem.get("MemTotal", 0)
        avail_kb = mem.get("MemAvailable", 0)
        used_kb = total_kb - avail_kb
        used_pct = round(used_kb / total_kb * 100, 1) if total_kb > 0 else 0
        avail_gb = round(avail_kb / 1024 / 1024, 2)
        status = "ok" if used_pct < 80 else "warning" if used_pct < 90 else "error"
        checks["memory"] = {"status": status, "usedPercent": used_pct, "availableGB": avail_gb}
        if status == "error":
            overall = "degraded"
    except Exception as e:
        checks["memory"] = {"status": "error", "message": str(e)}

    # Backend response time
    try:
        start = time.time()
        db = get_db()
        db.execute("SELECT COUNT(*) FROM tasks").fetchone()
        db.close()
        api_time = round((time.time() - start) * 1000, 1)
        status = "ok" if api_time < 200 else "warning" if api_time < 1000 else "error"
        checks["backend"] = {"status": status, "responseMs": api_time}
        if status == "error":
            overall = "degraded"
    except Exception as e:
        checks["backend"] = {"status": "error", "message": str(e)}
        overall = "degraded"

    # AI API check — 遍历已配置的 AI 供应商(数据库)
    # 不再读环境变量;通过 ApiKeyService.has_active_key 检测每 Provider
    try:
        from app.core.key_crypto import load_api_key_cipher
        from app.services.api_key_service import ApiKeyService

        db = get_db()
        cipher = load_api_key_cipher()
        svc = ApiKeyService(db=db, cipher=cipher)

        rows = db.execute(
            "SELECT provider_id FROM model_providers WHERE is_enabled=1 ORDER BY provider_id"
        ).fetchall()
        _ai_results: list[dict] = []
        for r in rows:
            pid = r["provider_id"]
            has_key = svc.has_active_key(provider_id=pid)
            _ai_results.append({
                "provider": pid,
                "hasActiveKey": has_key,
                "status": "ok" if has_key else "warning",
            })

        if not _ai_results:
            checks["aiApi"] = {"status": "skipped", "message": "无启用的供应商"}
        else:
            _ok_count = sum(1 for r in _ai_results if r["status"] == "ok")
            _warn_count = sum(1 for r in _ai_results if r["status"] == "warning")
            if _ok_count == 0:
                checks["aiApi"] = {"status": "warning", "count": len(_ai_results), "providers": _ai_results,
                                   "message": "所有启用的供应商都没有可用 Key"}
            else:
                checks["aiApi"] = {"status": "ok", "count": _ok_count,
                                   "providers": _ai_results,
                                   "warning_count": _warn_count}
    except Exception as e:
        logger.warning(f"AI API health check skipped: {e}")
        checks["aiApi"] = {"status": "skipped", "message": str(e)[:80]}

    return {
        "status": overall,
        "checks": checks,
    }


# Expose for uvicorn: "from app.main import app"
app = app_
