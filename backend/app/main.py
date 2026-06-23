"""
FastAPI application entry point.

The `app` package import triggers bootstrap (load_dotenv + setup_logging)
via its __init__.py. All subsequent imports are E402-clean.
"""

import asyncio
import logging
import os
import shutil
import subprocess
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Importing any app submodule triggers app/__init__.py bootstrap (load_dotenv + setup_logging)
from app.api import analysis, auth, evaluation, feedback, modeling, notifications, patents, solutions, tasks, workflow
from app.api import conversion as conversion_api
from app.api import kb_tools as kb_tools_api
from app.api import knowledge as knowledge_api
from app.api import knowledge_bases as knowledge_bases_api
from app.api import models as models_api
from app.api import users as users_api
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
from app.rate_limit import api_limiter, auth_limiter, get_client_ip, register_limiter

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

    if path == "/api/auth/login":
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
    """启动时运行数据库迁移、初始化模型注册表、知识库作业系统 + 专利向量表"""
    # 1. 运行 Alembic 数据库迁移（替代之前的手动 init_db）
    try:
        result = await asyncio.to_thread(
            lambda: subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        )
        if result.returncode == 0:
            logger.info("数据库迁移完成")
        else:
            logger.error(f"数据库迁移失败: {result.stderr}")
            raise RuntimeError(f"Alembic migration failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("数据库迁移超时（60秒）")
        raise
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

    # 1.5 注入 admin 用户记录（id=0），确保 FK 约束对 env 管理员可用
    try:
        from app.tables.pg_schema import seed_admin_user

        db = get_db()
        seed_admin_user(db)
        db.close()
        logger.info("管理员用户记录已确保存在")
    except Exception as e:
        logger.warning(f"注入管理员用户失败（非致命）: {e}")

    # 2. 加载模型注册表
    from app.algorithm.model_registry import model_registry

    await asyncio.to_thread(model_registry.load)
    logger.info("模型注册表已加载")

    # 4. 初始化知识库作业系统
    from app.services.knowledge_orchestration_service import knowledge_orchestration_service

    await knowledge_orchestration_service.start()
    logger.info("知识库作业系统已启动")

    # 5. 建专利向量表并重建所有向量（用 title + abstract）
    try:
        from app.algorithm.patent_search_engine import get_patent_search_engine, init_patent_vectors_table

        init_patent_vectors_table()
        engine = get_patent_search_engine()
        if engine.embedder:
            # 清除旧向量并重建
            db = get_db()
            db.execute("DELETE FROM patent_vectors")
            db.commit()
            count = await engine.backfill()
            logger.info("Patent vectors rebuilt", extra={"count": count})
            # 创建 HNSW 索引（仅 PostgreSQL，halfvec 支持 4096 维）
            if True:
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
    # 取消所有后台任务
    pending_tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in pending_tasks:
        t.cancel()
    logger.info("Shutdown complete")


app_.include_router(auth.router)
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
app_.include_router(users_api.router)
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

    # AI API check — 遍历所有已配置的 AI 供应商，分别报告健康状态
    _ai_results: list[dict] = []
    for env_key, val in sorted(os.environ.items()):
        upper = env_key.upper()
        if not (upper.startswith("AI_") and upper.endswith("_API_KEY") and val):
            continue
        provider_part = upper[3:-8]  # AI_{PROVIDER}_API_KEY
        host_env = f"AI_{provider_part}_API_HOST"
        ai_host = os.getenv(host_env, "https://api.deepseek.com")
        model_env = f"AI_{provider_part}_API_MODEL"
        ai_model = os.getenv(model_env, "deepseek-chat")

        provider_result: dict = {"provider": provider_part.lower(), "model": ai_model, "host": ai_host[:40]}
        try:
            import httpx
            from openai import OpenAI

            from app.algorithm.ai_client import pick_model

            client = OpenAI(
                api_key=val,
                base_url=ai_host,
                http_client=httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)),
            )
            start = time.time()
            client.chat.completions.create(
                model=pick_model(ai_model),
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            ai_time = round((time.time() - start) * 1000, 1)
            provider_result["status"] = "ok" if ai_time < 3000 else "warning"
            provider_result["responseMs"] = ai_time
        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "invalid" in err_msg.lower():
                provider_result["status"] = "error"
                provider_result["message"] = "Key无效或已过期"
            elif "429" in err_msg or "rate" in err_msg.lower():
                provider_result["status"] = "warning"
                provider_result["message"] = "请求限流"
            elif "insufficient" in err_msg or "exceeded" in err_msg.lower():
                provider_result["status"] = "warning"
                provider_result["message"] = "额度不足"
            else:
                provider_result["status"] = "error"
                provider_result["message"] = err_msg[:60]
        _ai_results.append(provider_result)

    if not _ai_results:
        checks["aiApi"] = {"status": "skipped", "message": "未配置任何 API Key"}
    else:
        _ok_count = sum(1 for r in _ai_results if r["status"] == "ok")
        _err_count = sum(1 for r in _ai_results if r["status"] == "error")
        if _err_count == len(_ai_results):
            checks["aiApi"] = {"status": "error", "count": len(_ai_results), "providers": _ai_results}
        elif _err_count > 0:
            checks["aiApi"] = {"status": "warning", "count": len(_ai_results), "providers": _ai_results}
        else:
            checks["aiApi"] = {"status": "ok", "count": len(_ai_results), "providers": _ai_results}
        # AI API 失败不影响系统整体健康状态（它是可选服务）
        # overall 不因为 AI API 而降级

    return {
        "status": overall,
        "checks": checks,
    }


# Expose for uvicorn: "from app.main import app"
app = app_
