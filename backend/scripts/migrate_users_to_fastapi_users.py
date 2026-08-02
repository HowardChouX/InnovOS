"""一次性数据迁移脚本：users 表从旧 schema 迁移到 FastAPI Users schema。

One-shot 脚本：运行后从仓库删除，不留在生产启动路径。
运行前必须先执行 `alembic upgrade head`（DDL 已应用）。

步骤：
1. 列名迁移：password_hash -> hashed_password（RENAME COLUMN）
2. role='admin' -> is_superuser=True
3. email 为空的用户补占位邮箱 {username}@local.invalid
4. user_id=0 的幽灵管理员引用归并到真实管理员 id
5. 删除 id=0 幽灵行

超级用户不再由脚本/环境变量种子化，需开发者手动在数据库中设置。

用法：
    cd backend
    python scripts/migrate_users_to_fastapi_users.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2  # noqa: E402
from app.core.config import settings  # noqa: E402


def run():
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # 1. 列名迁移
        print("[1/5] 重命名 password_hash -> hashed_password ...")
        cur.execute(
            "ALTER TABLE users RENAME COLUMN password_hash TO hashed_password"
        )

        # 2. 管理员标志
        print("[2/5] role='admin' -> is_superuser=True ...")
        cur.execute(
            "UPDATE users SET is_superuser = TRUE WHERE role = 'admin'"
        )

        # 3. email 补全
        print("[3/5] 补全空 email 为 {username}@local.invalid ...")
        cur.execute(
            "UPDATE users SET email = username || '@local.invalid' "
            "WHERE email IS NULL OR email = ''"
        )

        # 4. 幽灵管理员引用归并
        # 先确定真实管理员 id（第一个 is_superuser=TRUE 的用户）
        cur.execute(
            "SELECT id FROM users WHERE is_superuser = TRUE ORDER BY id LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            print("[4/5] 未找到 is_superuser=TRUE 的管理员，跳过归并 id=0 引用")
            real_admin_id = None
        else:
            real_admin_id = row[0]
            print(f"[4/5] 归并 user_id=0 引用到真实管理员 id={real_admin_id} ...")
            for table in [
                "tasks", "evaluations", "feedbacks", "audit_log",
                "notifications", "knowledge_bases", "knowledge_items",
                "knowledge_vectors", "knowledge_jobs", "knowledge_groups",
                "knowledge_docs",
            ]:
                try:
                    cur.execute(
                        f"UPDATE {table} SET user_id = %s WHERE user_id = 0",
                        (real_admin_id,),
                    )
                except Exception:
                    print(f"  (跳过 {table})")

        # 5. 删除幽灵行
        print("[5/5] 删除 id=0 幽灵管理员行 ...")
        cur.execute("DELETE FROM users WHERE id = 0")

        conn.commit()
        print("数据迁移完成")
    except Exception as e:
        conn.rollback()
        print(f"迁移失败，已回滚: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()