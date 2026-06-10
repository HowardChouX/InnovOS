import os
from dotenv import load_dotenv

# 从 backend/ 目录加载 .env，不依赖 CWD
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path)
import logging
import sys

# 日志配置：INFO 及以上输出到终端（让知识库索引等后台 job 日志可见）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)

import shutil
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, get_db
from app.api import auth, tasks, analysis, patents, solutions, workflow, evaluation, feedback, notifications, knowledge as knowledge_api, knowledge_bases as knowledge_bases_api, modeling, models as models_api, kb_tools as kb_tools_api
from app.api.sidebar import router as sidebar_router
from app.api.admin import router as admin_router
from app.api.workflow_steps import router as workflow_steps_router
from app.seed import seed_admin_user, seed_patents
from app.algorithm.model_registry import model_registry

init_db()
seed_admin_user()
seed_patents()
model_registry.load()  # 加载全量模型注册表

app = FastAPI(title="InnovOS API", description="创新智能平台后端 API")


@app.on_event("startup")
async def startup():
    """启动时初始化知识库作业系统（崩溃恢复）"""
    from app.services.knowledge_orchestration_service import knowledge_orchestration_service
    await knowledge_orchestration_service.start()
    logger = logging.getLogger(__name__)
    logger.info("Knowledge job system started — recovered stalled jobs")

# 开发环境 CORS（生产环境通过 nginx 同源代理，无需 CORS）
dev_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in dev_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(analysis.router)
app.include_router(patents.router)
app.include_router(solutions.router)
app.include_router(workflow.router)
app.include_router(evaluation.router)
app.include_router(feedback.router)
app.include_router(admin_router)
app.include_router(notifications.router)
app.include_router(sidebar_router)
app.include_router(knowledge_api.router)
app.include_router(knowledge_bases_api.router)
app.include_router(kb_tools_api.router)
app.include_router(models_api.router)
app.include_router(modeling.router)
app.include_router(workflow_steps_router)


@app.get("/api/health")
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
        with open("/proc/meminfo", "r") as f:
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

    # AI API check
    try:
        from app.algorithm.key_manager import key_manager
        keys = key_manager.list_keys()
        active_keys = [k for k in keys if k.get("is_active")]

        if not active_keys:
            checks["aiApi"] = {"status": "skipped", "message": "未配置API Key"}
        else:
            from openai import OpenAI
            from app.algorithm.crypto import decrypt_key
            from app.algorithm.ai_client import pick_model

            key = active_keys[0]
            decrypted_key = decrypt_key(key["api_key"])
            client = OpenAI(api_key=decrypted_key, base_url=key["api_base_url"])

            start = time.time()
            resp = client.chat.completions.create(
                model=pick_model(key["api_model"]),
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            ai_time = round((time.time() - start) * 1000, 1)
            status = "ok" if ai_time < 3000 else "warning" if ai_time < 10000 else "error"
            checks["aiApi"] = {"status": status, "responseMs": ai_time, "message": key["key_name"]}
            if status == "error":
                overall = "degraded"
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "invalid" in err_msg.lower():
            checks["aiApi"] = {"status": "error", "message": "Key无效"}
        elif "429" in err_msg or "rate" in err_msg.lower():
            checks["aiApi"] = {"status": "warning", "message": "限流"}
        elif "insufficient" in err_msg or "exceeded" in err_msg.lower():
            checks["aiApi"] = {"status": "warning", "message": "额度不足"}
        else:
            checks["aiApi"] = {"status": "error", "message": err_msg[:50]}
        overall = "degraded"

    return {
        "status": overall,
        "checks": checks,
    }
