#!/usr/bin/env python3
"""
PostgreSQL 数据迁移脚本 — 从 SQLite 迁移到 PostgreSQL。

用法：
    # 1. 启动 PostgreSQL（docker compose up -d postgres）
    # 2. 运行迁移：
    DATABASE_URL=postgresql://innovos:innovos_secret@localhost:5432/innovos \
    python scripts/migrate_data.py

环境变量：
    SQLITE_PATH    — SQLite 数据库路径（默认 backend/InnovOS_ACCOUNTS.db）
    DATABASE_URL   — PostgreSQL 连接串

流程：
    1. 连接 SQLite 读取所有表数据
    2. 连接 PostgreSQL 并初始化 schema
    3. 逐表迁移，自动处理 ID 序列和类型转换
    4. 验证数据完整性

注意：
    - 迁移是幂等的（先清空 PostgreSQL 目标表）
    - UUID 主键表（knowledge_bases, knowledge_items, knowledge_groups）直接复制
    - SERIAL 主键表重置序列到 max(id) + 1
"""
import os
import sys
import json
import logging

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("migrate")

# ─── 所有表及其迁移配置 ──────────────────────────────────────
# 迁移顺序必须遵守外键依赖
TABLES = [
    # (显示名, sqlite_table, pg_table, columns, row_mapper)
    # columns: [(pg_column, sqlite_column, type_hint), ...]
    #   type_hint: "int" | "text" | "json" | "raw" | "skip"
    #   - "int": 确保是整数
    #   - "text": 直接复制字符串
    #   - "json": json.dumps 序列化（SQLite 可能存了 dict/list）
    #   - "raw": 直接复制
    #   - "skip": 不复制该列
    # row_mapper: 对整行做额外转换的函数（或 None）
    ("users", "users", "users", [
        ("id", "id", "int"),
        ("username", "username", "text"),
        ("password_hash", "password_hash", "text"),
        ("role", "role", "text"),
        ("email", "email", "text"),
        ("is_active", "is_active", "int"),
        ("created_at", "created_at", "text"),
    ], None),
    ("tasks", "tasks", "tasks", [
        ("id", "id", "int"),
        ("user_id", "user_id", "int"),
        ("title", "title", "text"),
        ("description", "description", "text"),
        ("tags", "tags", "text"),
        ("status", "status", "text"),
        ("created_at", "created_at", "text"),
        ("updated_at", "updated_at", "text"),
    ], None),
    ("analyses", "analyses", "analyses", [
        ("id", "id", "int"),
        ("task_id", "task_id", "int"),
        ("center_node", "center_node", "text"),
        ("satellite_nodes", "satellite_nodes", "text"),
        ("edges", "edges", "text"),
        ("principles", "principles", "text"),
    ], None),
    ("solutions", "solutions", "solutions", [
        ("id", "id", "int"),
        ("task_id", "task_id", "int"),
        ("title", "title", "text"),
        ("description", "description", "text"),
        ("principles", "principles", "text"),
        ("confidence_score", "confidence_score", "int"),
        ("patent_references", "patent_references", "text"),
        ("rating", "rating", "int"),
    ], None),
    ("workflows", "workflows", "workflows", [
        ("id", "id", "int"),
        ("task_id", "task_id", "int"),
        ("status", "status", "text"),
        ("steps", "steps", "text"),
        ("created_at", "created_at", "text"),
    ], None),
    ("patents", "patents", "patents", [
        ("id", "id", "int"),
        ("title", "title", "text"),
        ("abstract", "abstract", "text"),
        ("applicants", "applicants", "text"),
        ("inventors", "inventors", "text"),
        ("filing_date", "filing_date", "text"),
        ("publication_date", "publication_date", "text"),
        ("patent_number", "patent_number", "text"),
        ("ipc_codes", "ipc_codes", "text"),
        ("relevance_score", "relevance_score", "int"),
    ], None),
    ("evaluations", "evaluations", "evaluations", [
        ("id", "id", "int"),
        ("solution_id", "solution_id", "int"),
        ("user_id", "user_id", "int"),
        ("dimension", "dimension", "text"),
        ("score", "score", "text"),
        ("details", "details", "text"),
        ("status", "status", "text"),
        ("created_at", "created_at", "text"),
        ("root_cause_cut", "root_cause_cut", "int"),
        ("original_contradiction_resolved", "original_contradiction_resolved", "int"),
        ("new_contradictions", "new_contradictions", "text"),
        ("function_deficits_filled", "function_deficits_filled", "text"),
        ("new_harmful_interactions", "new_harmful_interactions", "text"),
        ("ifr_distance", "ifr_distance", "text"),
        ("ifr_gap_description", "ifr_gap_description", "text"),
        ("ifr_parameters_achieved", "ifr_parameters_achieved", "text"),
        ("overall_verdict", "overall_verdict", "text"),
        ("evolution_alignment", "evolution_alignment", "text"),
        ("aligned_laws", "aligned_laws", "text"),
        ("misaligned_laws", "misaligned_laws", "text"),
        ("maturity", "maturity", "text"),
        ("confidence", "confidence", "raw"),
    ], None),
    ("feedbacks", "feedbacks", "feedbacks", [
        ("id", "id", "int"),
        ("user_id", "user_id", "int"),
        ("solution_id", "solution_id", "int"),
        ("rating", "rating", "int"),
        ("feedback_type", "feedback_type", "text"),
        ("comments", "comments", "text"),
        ("is_applied", "is_applied", "int"),
        ("created_at", "created_at", "text"),
    ], None),
    ("audit_logs", "audit_logs", "audit_logs", [
        ("id", "id", "int"),
        ("user_id", "user_id", "raw"),
        ("action", "action", "text"),
        ("resource_type", "resource_type", "text"),
        ("resource_id", "resource_id", "raw"),
        ("detail", "detail", "text"),
        ("ip_address", "ip_address", "text"),
        ("status", "status", "text"),
        ("created_at", "created_at", "text"),
    ], None),
    ("api_keys", "api_keys", "api_keys", [
        ("id", "id", "int"),
        ("provider_id", "provider_id", "text"),
        ("key_name", "key_name", "text"),
        ("api_key", "api_key", "text"),
        ("api_base_url", "api_base_url", "text"),
        ("api_model", "api_model", "text"),
        ("is_active", "is_active", "int"),
        ("priority", "priority", "int"),
        ("max_rpm", "max_rpm", "int"),
        ("current_rpm", "current_rpm", "int"),
        ("last_reset_at", "last_reset_at", "raw"),
        ("last_used_at", "last_used_at", "raw"),
        ("request_count", "request_count", "int"),
        ("created_at", "created_at", "text"),
    ], None),
    ("notifications", "notifications", "notifications", [
        ("id", "id", "int"),
        ("user_id", "user_id", "int"),
        ("title", "title", "text"),
        ("content", "content", "text"),
        ("type", "type", "text"),
        ("is_read", "is_read", "int"),
        ("is_recalled", "is_recalled", "int"),
        ("created_at", "created_at", "text"),
    ], None),
    ("model_providers", "model_providers", "model_providers", [
        ("id", "id", "int"),
        ("provider_id", "provider_id", "text"),
        ("name", "name", "text"),
        ("protocol", "protocol", "text"),
        ("api_host", "api_host", "text"),
        ("api_key_encrypted", "api_key_encrypted", "raw"),
        ("api_model", "api_model", "text"),
        ("models", "models", "text"),
        ("priority", "priority", "int"),
        ("max_rpm", "max_rpm", "int"),
        ("current_rpm", "current_rpm", "int"),
        ("request_count", "request_count", "int"),
        ("is_enabled", "is_enabled", "int"),
        ("last_used_at", "last_used_at", "raw"),
        ("last_reset_at", "last_reset_at", "raw"),
        ("created_at", "created_at", "text"),
    ], None),
    ("knowledge_bases", "knowledge_bases", "knowledge_bases", [
        ("id", "id", "text"),
        ("user_id", "user_id", "int"),
        ("name", "name", "text"),
        ("group_id", "group_id", "raw"),
        ("dimensions", "dimensions", "raw"),
        ("embedding_model_id", "embedding_model_id", "raw"),
        ("status", "status", "text"),
        ("error", "error", "raw"),
        ("rerank_model_id", "rerank_model_id", "raw"),
        ("file_processor_id", "file_processor_id", "raw"),
        ("chunk_size", "chunk_size", "int"),
        ("chunk_overlap", "chunk_overlap", "int"),
        ("threshold", "threshold", "raw"),
        ("document_count", "document_count", "raw"),
        ("search_mode", "search_mode", "text"),
        ("hybrid_alpha", "hybrid_alpha", "raw"),
        ("created_at", "created_at", "text"),
        ("updated_at", "updated_at", "text"),
    ], None),
    ("knowledge_items", "knowledge_items", "knowledge_items", [
        ("id", "id", "text"),
        ("base_id", "base_id", "text"),
        ("group_id", "group_id", "raw"),
        ("type", "type", "text"),
        ("data", "data", "text"),
        ("status", "status", "text"),
        ("error", "error", "raw"),
        ("created_at", "created_at", "text"),
        ("updated_at", "updated_at", "text"),
    ], None),
    ("knowledge_groups", "knowledge_groups", "knowledge_groups", [
        ("id", "id", "text"),
        ("user_id", "user_id", "int"),
        ("name", "name", "text"),
        ("created_at", "created_at", "text"),
        ("updated_at", "updated_at", "text"),
    ], None),
    ("knowledge_docs", "knowledge_docs", "knowledge_docs", [
        ("id", "id", "int"),
        ("title", "title", "text"),
        ("content", "content", "text"),
        ("category", "category", "text"),
        ("tags", "tags", "text"),
        ("source", "source", "text"),
        ("doc_type", "doc_type", "text"),
        ("user_id", "user_id", "int"),
        ("base_id", "base_id", "int"),
        ("is_active", "is_active", "int"),
        ("created_at", "created_at", "text"),
        ("updated_at", "updated_at", "text"),
    ], None),
    ("problem_modelings", "problem_modelings", "problem_modelings", [
        ("id", "id", "int"),
        ("task_id", "task_id", "int"),
        ("problem_elements", "problem_elements", "text"),
        ("conflicts", "conflicts", "text"),
        ("recommended_principles", "recommended_principles", "text"),
        ("innovation_directions", "innovation_directions", "text"),
        ("model_structure", "model_structure", "text"),
    ], None),
]

# 需要重置序列的 SERIAL 主键表
SERIAL_TABLES = [
    "users", "tasks", "analyses", "solutions", "workflows",
    "patents", "evaluations", "feedbacks", "audit_logs",
    "api_keys", "notifications", "model_providers",
    "knowledge_docs", "problem_modelings",
]


def main():
    sqlite_path = os.getenv("SQLITE_PATH", "")
    if not sqlite_path:
        sqlite_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "InnovOS_ACCOUNTS.db",
        )
    pg_url = os.getenv("DATABASE_URL", "")

    if not pg_url:
        logger.error("请设置 DATABASE_URL 环境变量")
        sys.exit(1)

    # ── 连接 SQLite ────────────────────────────────────
    import sqlite3
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite 数据库不存在: {sqlite_path}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    logger.info(f"✅ 已连接 SQLite: {sqlite_path}")

    # ── 连接 PostgreSQL ────────────────────────────────
    import psycopg2
    import psycopg2.extras

    pg_conn = psycopg2.connect(pg_url)
    pg_conn.autocommit = False
    logger.info(f"✅ 已连接 PostgreSQL")

    try:
        # ── 初始化 schema ──────────────────────────────
        logger.info("初始化 PostgreSQL schema...")
        from app.database import get_db
        # 直接使用 pg_schema 初始化
        from app.tables.pg_schema import init_all_tables
        db = get_db()
        try:
            init_all_tables(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        logger.info("PostgreSQL schema 就绪")

        # ── 逐表迁移 ────────────────────────────────────
        total_rows = 0
        for display_name, sqlite_table, pg_table, columns, row_mapper in TABLES:
            count = _migrate_table(
                sqlite_conn, pg_conn, pg_table, sqlite_table, columns, row_mapper
            )
            total_rows += count

        # ── 重置序列 ────────────────────────────────────
        for table in SERIAL_TABLES:
            _reset_sequence(pg_conn, table)

        pg_conn.commit()
        logger.info(f"\n🎉 迁移完成！共迁移 {total_rows} 条记录")

        # ── 验证 ────────────────────────────────────────
        _validate(pg_conn, sqlite_conn)

    except Exception as e:
        pg_conn.rollback()
        logger.exception(f"迁移失败: {e}")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()


def _migrate_table(
    sqlite_conn, pg_conn, pg_table, sqlite_table, columns, row_mapper
):
    """迁移单表数据。"""
    # 读取 SQLite 数据
    cur = sqlite_conn.execute(f"SELECT * FROM {sqlite_table}")
    rows = cur.fetchall()
    if not rows:
        logger.info(f"  ⏭  {pg_table}: 0 条（空表）")
        return 0

    # 清空 PostgreSQL 目标表
    pg_cur = pg_conn.cursor()
    pg_cur.execute(f"TRUNCATE TABLE {pg_table} CASCADE")
    pg_cur.close()

    # 准备列名
    pg_cols = [c[0] for c in columns if c[3] != "skip"]
    sqlite_cols = [c[1] for c in columns if c[3] != "skip"]
    type_hints = [c[3] for c in columns if c[3] != "skip"]

    placeholders = ",".join("%s" for _ in pg_cols)
    col_names = ",".join(pg_cols)
    insert_sql = f"INSERT INTO {pg_table} ({col_names}) VALUES ({placeholders})"

    pg_cur = pg_conn.cursor()
    count = 0
    for row in rows:
        try:
            values = []
            for col, hint in zip(sqlite_cols, type_hints):
                val = row[col] if col in row.keys() else None
                if val is None:
                    values.append(None)
                elif hint == "int":
                    values.append(int(val))
                elif hint == "text":
                    values.append(str(val))
                elif hint == "json":
                    if isinstance(val, (dict, list)):
                        values.append(json.dumps(val, ensure_ascii=False))
                    else:
                        # 已经是字符串形式的 JSON
                        values.append(str(val))
                else:
                    values.append(val)

            if row_mapper:
                values = row_mapper(row, values)

            pg_cur.execute(insert_sql, values)
            count += 1
        except Exception as e:
            logger.warning(f"  ⚠  {pg_table} 行 {count + 1} 失败: {e}")
            logger.warning(f"     数据: {dict(row)}")
            continue

    pg_cur.close()
    logger.info(f"  ✅ {pg_table}: {count} 条")
    return count


def _reset_sequence(pg_conn, table):
    """重置 SERIAL 序列到 max(id) + 1。"""
    cur = pg_conn.cursor()
    try:
        cur.execute(f"SELECT MAX(id) FROM {table}")
        row = cur.fetchone()
        max_id = row[0] if row and row[0] else 0
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), %s, false)",
            (max_id + 1,),
        )
    except Exception as e:
        logger.debug(f"  序列重置跳过 {table}: {e}")
    finally:
        cur.close()


def _validate(pg_conn, sqlite_conn):
    """验证数据完整性。"""
    logger.info("\n── 验证 ──")
    cur = pg_conn.cursor()
    all_ok = True
    for _, sqlite_table, pg_table, _, _ in TABLES:
        try:
            # PostgreSQL count
            cur.execute(f"SELECT COUNT(*) FROM {pg_table}")
            pg_count = cur.fetchone()[0]

            # SQLite count
            sq_row = sqlite_conn.execute(
                f"SELECT COUNT(*) FROM {sqlite_table}"
            ).fetchone()
            sq_count = sq_row[0] if sq_row else 0

            status = "✅" if pg_count == sq_count else "⚠"
            if pg_count != sq_count:
                all_ok = False
            logger.info(f"  {status} {pg_table}: PG={pg_count} SQLite={sq_count}")
        except Exception as e:
            logger.warning(f"  ?  {pg_table}: 验证失败 - {e}")

    cur.close()
    if all_ok:
        logger.info("🎉 所有表数据一致！")
    else:
        logger.warning("某些表数据条数不一致，请检查上方的 ⚠ 标记")


if __name__ == "__main__":
    main()
