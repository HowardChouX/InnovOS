import os
import time
import platform
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from app.auth import get_current_user, require_admin
from app.database import get_db

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

_start_time = time.time()


def _get_user_filter(user: dict) -> str:
    """根据用户角色返回 SQL 过滤条件"""
    if user["role"] == "admin":
        return "", ()
    return "AND t.user_id = ?", (user["id"],)


@router.get("/overview")
def get_overview(user: dict = Depends(get_current_user)):
    """总览数据（数据隔离：普通用户只看自己的）"""
    db = get_db()

    if user["role"] == "admin":
        total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        completed = db.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
        failed = db.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0]
        total_analyses = db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        total_solutions = db.execute("SELECT COUNT(*) FROM solutions").fetchone()[0]
        avg_rating = db.execute("SELECT AVG(rating) FROM solutions WHERE rating > 0").fetchone()[0] or 0
    else:
        total_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (user["id"],)).fetchone()[0]
        completed = db.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='completed'", (user["id"],)).fetchone()[0]
        failed = db.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='failed'", (user["id"],)).fetchone()[0]
        total_analyses = db.execute(
            "SELECT COUNT(*) FROM analyses a JOIN tasks t ON a.task_id=t.id WHERE t.user_id=?",
            (user["id"],)
        ).fetchone()[0]
        total_solutions = db.execute(
            "SELECT COUNT(*) FROM solutions s JOIN tasks t ON s.task_id=t.id WHERE t.user_id=?",
            (user["id"],)
        ).fetchone()[0]
        avg_rating = db.execute(
            "SELECT AVG(s.rating) FROM solutions s JOIN tasks t ON s.task_id=t.id WHERE t.user_id=? AND s.rating > 0",
            (user["id"],)
        ).fetchone()[0] or 0

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
def get_task_stats(user: dict = Depends(get_current_user)):
    """任务统计（数据隔离）"""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    if user["role"] == "admin":
        by_status = db.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
        ).fetchall()
        recent = db.execute(
            "SELECT date(created_at) as d, COUNT(*) as cnt FROM tasks "
            "WHERE created_at >= ? GROUP BY date(created_at) ORDER BY d",
            (cutoff,)
        ).fetchall()
    else:
        by_status = db.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE user_id=? GROUP BY status",
            (user["id"],)
        ).fetchall()
        recent = db.execute(
            "SELECT date(created_at) as d, COUNT(*) as cnt FROM tasks "
            "WHERE user_id=? AND created_at >= ? GROUP BY date(created_at) ORDER BY d",
            (user["id"], cutoff)
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
def get_key_stats(user: dict = Depends(require_admin)):
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
def get_system_status(user: dict = Depends(require_admin)):
    """系统状态（仅管理员）"""
    db = get_db()

    # 运行时间
    uptime_secs = int(time.time() - _start_time)
    days = uptime_secs // 86400
    hours = (uptime_secs % 86400) // 3600
    mins = (uptime_secs % 3600) // 60
    uptime_str = f"{days}d {hours}h {mins}m"

    # 数据库大小
    from app.database import get_db, is_postgres, get_sqlite_path
    db = get_db()
    try:
        if is_postgres():
            row = db.execute("SELECT pg_database_size(current_database()) AS size").fetchone()
            db_size = row["size"] if row else 0
        else:
            db_path = get_sqlite_path()
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", db_path)
            db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        if db_size > 1024 * 1024:
            db_size_str = f"{db_size / 1024 / 1024:.1f} MB"
        elif db_size > 1024:
            db_size_str = f"{db_size / 1024:.1f} KB"
        else:
            db_size_str = f"{db_size} B"
    finally:
        db.close()

    # 内存使用（Linux /proc/meminfo）
    memory_info = {"total": 0, "used": 0, "percent": 0}
    try:
        with open("/proc/meminfo", "r") as f:
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
        with open("/proc/stat", "r") as f:
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
            "version": "1.0.0",
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
