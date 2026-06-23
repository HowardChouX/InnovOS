import platform
import time as _time_module
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SuperUserDep
from app.core.config import settings
from app.database import get_db

router = APIRouter(prefix="/monitor", tags=["monitor"])

_start_time = _time_module.monotonic()


@router.get("/overview")
def get_overview(current_user: CurrentUser):
    """总览数据（数据隔离：普通用户只看自己的）"""
    db = get_db()

    if current_user.role == "admin":
        total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        completed = db.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
        failed = db.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0]
        total_analyses = db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        total_solutions = db.execute("SELECT COUNT(*) FROM solutions").fetchone()[0]
        avg_rating = db.execute("SELECT AVG(rating) FROM solutions WHERE rating > 0").fetchone()[0] or 0
    else:
        uid = current_user.id
        total_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (uid,)).fetchone()[0]
        completed = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='completed'", (uid,)
        ).fetchone()[0]
        failed = db.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='failed'", (uid,)).fetchone()[
            0
        ]
        total_analyses = db.execute(
            "SELECT COUNT(*) FROM analyses a JOIN tasks t ON a.task_id=t.id WHERE t.user_id=?", (uid,)
        ).fetchone()[0]
        total_solutions = db.execute(
            "SELECT COUNT(*) FROM solutions s JOIN tasks t ON s.task_id=t.id WHERE t.user_id=?", (uid,)
        ).fetchone()[0]
        avg_rating = (
            db.execute(
                "SELECT AVG(s.rating) FROM solutions s JOIN tasks t ON s.task_id=t.id WHERE t.user_id=? AND s.rating > 0",
                (uid,),
            ).fetchone()[0]
            or 0
        )

    db.close()

    success_rate = round((completed / total_tasks * 100), 1) if total_tasks > 0 else 0

    return {
        "data": {
            "totalTasks": total_tasks,
            "completedTasks": completed,
            "failedTasks": failed,
            "successRate": success_rate,
            "totalAnalyses": total_analyses,
            "totalSolutions": total_solutions,
            "avgRating": round(avg_rating, 1),
        },
        "message": "success",
    }


@router.get("/tasks")
def get_task_stats(current_user: CurrentUser):
    """任务统计（数据隔离）"""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    if current_user.role == "admin":
        by_status = db.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall()
        recent = db.execute(
            "SELECT date(created_at) as d, COUNT(*) as cnt FROM tasks "
            "WHERE created_at >= ? GROUP BY date(created_at) ORDER BY d",
            (cutoff,),
        ).fetchall()
    else:
        uid = current_user.id
        by_status = db.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE user_id=? GROUP BY status", (uid,)
        ).fetchall()
        recent = db.execute(
            "SELECT date(created_at) as d, COUNT(*) as cnt FROM tasks "
            "WHERE user_id=? AND created_at >= ? GROUP BY date(created_at) ORDER BY d",
            (uid, cutoff),
        ).fetchall()

    db.close()

    return {
        "data": {
            "byStatus": {r["status"]: r["cnt"] for r in by_status},
            "recent7days": [{"date": r["d"], "count": r["cnt"]} for r in recent],
        },
        "message": "success",
    }


@router.get("/keys")
def get_key_stats(_admin: SuperUserDep):
    """Key 使用统计（仅管理员）"""
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM api_keys WHERE is_active=1").fetchone()[0]
    total_requests = db.execute("SELECT COALESCE(SUM(request_count), 0) FROM api_keys").fetchone()[0]

    keys = db.execute(
        "SELECT id, key_name, request_count, current_rpm, max_rpm, is_active FROM api_keys ORDER BY request_count DESC"
    ).fetchall()

    db.close()

    return {
        "data": {
            "totalKeys": total,
            "activeKeys": active,
            "totalRequests": total_requests,
            "keyUsage": [
                {
                    "id": k["id"],
                    "name": k["key_name"],
                    "requests": k["request_count"],
                    "rpm": k["current_rpm"],
                    "maxRpm": k["max_rpm"],
                    "isActive": bool(k["is_active"]),
                }
                for k in keys
            ],
        },
        "message": "success",
    }


@router.get("/system")
def get_system_status(_admin: SuperUserDep):
    """系统状态（仅管理员）"""
    db = get_db()

    # 运行时间
    uptime_secs = int(_time_module.monotonic() - _start_time)
    days = uptime_secs // 86400
    hours = (uptime_secs % 86400) // 3600
    mins = (uptime_secs % 3600) // 60
    uptime_str = f"{days}d {hours}h {mins}m"

    # 数据库大小
    try:
        row = db.execute("SELECT pg_database_size(current_database()) AS size").fetchone()
        db_size = row["size"] if row else 0
        if db_size > 1024 * 1024:
            db_size_str = f"{db_size / 1024 / 1024:.1f} MB"
        elif db_size > 1024:
            db_size_str = f"{db_size / 1024:.1f} KB"
        else:
            db_size_str = f"{db_size} B"
    except Exception:
        db_size_str = "N/A"

    # 内存使用（Linux /proc/meminfo，非 Linux 返回默认值）
    memory_info = {"total": 0, "used": 0, "percent": 0}
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:"):
                    mem[parts[0].rstrip(":")] = int(parts[1])  # KB
            total_kb = mem.get("MemTotal", 0)
            avail_kb = mem.get("MemAvailable", 0)
            used_kb = total_kb - avail_kb
            memory_info = {
                "total": f"{total_kb / 1024 / 1024:.1f} GB",
                "used": f"{used_kb / 1024 / 1024:.1f} GB",
                "percent": round(used_kb / total_kb * 100, 1) if total_kb > 0 else 0,
            }
    except Exception:
        memory_info = {"total": "-", "used": "-", "percent": 0}

    # CPU 信息
    cpu_info = {"cores": 0, "usage": 0}
    try:
        import multiprocessing

        cpu_info["cores"] = multiprocessing.cpu_count()
        # 简易 CPU 使用率（读取 /proc/stat）
        with open("/proc/stat") as f:
            line = f.readline()
            parts = line.split()
            idle = int(parts[4])
            total = sum(int(p) for p in parts[1:])
            cpu_info["usage"] = round((1 - idle / total) * 100, 1) if total > 0 else 0
    except Exception:
        cpu_info = {"cores": 0, "usage": 0}

    # AI 调用统计
    ai_stats = {"totalCalls": 0, "successCalls": 0, "failedCalls": 0}
    try:
        total_analyses = db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        total_solutions = db.execute("SELECT COUNT(*) FROM solutions").fetchone()[0]
        total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
        failed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0]

        ai_stats = {
            "totalCalls": total_analyses + total_solutions,
            "successCalls": completed_tasks,
            "failedCalls": failed_tasks,
        }
    except Exception:
        pass

    # 数据库统计
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    total_patents = db.execute("SELECT COUNT(*) FROM patents").fetchone()[0]
    total_keys = db.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
    active_keys = db.execute("SELECT COUNT(*) FROM api_keys WHERE is_active=1").fetchone()[0]

    db.close()

    return {
        "data": {
            "uptime": uptime_str,
            "version": getattr(settings, "APP_VERSION", "0.3.0"),
            "pythonVersion": platform.python_version(),
            "platform": platform.system(),
            # 数据库
            "dbSize": db_size_str,
            "totalUsers": total_users,
            "totalTasks": total_tasks,
            "totalPatents": total_patents,
            "apiKeys": f"{active_keys}/{total_keys}",
            # 系统资源
            "memory": memory_info,
            "cpu": cpu_info,
            # AI 统计
            "aiStats": ai_stats,
        },
        "message": "success",
    }
