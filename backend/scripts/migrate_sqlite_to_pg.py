#!/usr/bin/env python3
"""
SQLite → PostgreSQL 数据迁移脚本。

用法：
  cd backend && python3 scripts/migrate_sqlite_to_pg.py

说明：
  读取 SQLite (InnovOS_ACCOUNTS.db) 的所有数据，
  写入 PostgreSQL (由 DATABASE_URL 环境变量指定)。

处理 schema 差异：
  - models 表：PG 无自增 id，用 (provider_id, model_id) 作复合主键
  - knowledge_vectors: PG 的 embedding 列是 vector(4096)，插入 JSON 数组字符串
  - 自动重置 PG 序列
"""

import os
import sys
import json
import sqlite3
import logging

import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("migrate")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "InnovOS_ACCOUNTS.db")
PG_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://innovos:innovos_secret@localhost:5432/innovos",
)

# ──────────────────────────────────────────────
# 表定义：读取顺序 + 列映射
# ──────────────────────────────────────────────

TABLES = [
    # (table_name, sqlite_select, pg_insert, on_conflict)
    {
        "name": "users",
        # Include id to preserve FK references from other tables
        "columns": ["id", "username", "password_hash", "role", "email", "is_active", "created_at"],
        "pk": "id",
    },
    {
        "name": "patents",
        "columns": ["id", "title", "abstract", "applicants", "inventors",
                     "filing_date", "publication_date", "patent_number",
                     "ipc_codes", "relevance_score"],
        "pk": "id",
    },
    {
        "name": "model_providers",
        "columns": ["id", "provider_id", "name", "protocol", "api_host",
                     "api_key_encrypted", "api_model", "models",
                     "max_rpm", "current_rpm", "request_count",
                     "is_enabled", "last_used_at", "last_reset_at", "created_at"],
        "pk": "id",
    },
    {
        "name": "models",
        # PG 无自增 id，用 (provider_id, model_id) 复合主键
        "columns": ["provider_id", "model_id", "name", "capabilities",
                     "endpoint_types", "context_window", "max_output_tokens",
                     "max_input_tokens", "model_group", "is_enabled", "metadata"],
        "pk": None,  # composite key
    },
    {
        "name": "knowledge_groups",
        "columns": ["id", "user_id", "name", "created_at", "updated_at"],
        "pk": "id",  # UUID text, no sequence
    },
    {
        "name": "knowledge_bases",
        "columns": ["id", "user_id", "name", "group_id", "dimensions",
                     "embedding_model_id", "status", "error", "rerank_model_id",
                     "file_processor_id", "chunk_size", "chunk_overlap",
                     "threshold", "document_count", "search_mode",
                     "hybrid_alpha", "created_at", "updated_at"],
        "pk": "id",  # UUID text, no sequence
    },
    {
        "name": "api_keys",
        "columns": ["id", "provider_id", "key_name", "api_key", "api_base_url",
                     "api_model", "is_active", "priority", "max_rpm",
                     "current_rpm", "last_reset_at", "last_used_at",
                     "request_count", "created_at"],
        "pk": "id",
    },
    {
        "name": "notifications",
        "columns": ["id", "user_id", "title", "content", "type", "is_read",
                     "is_recalled", "created_at"],
        "pk": "id",
    },
    {
        "name": "knowledge_docs",
        "columns": ["id", "title", "content", "category", "tags", "source",
                     "doc_type", "user_id", "base_id", "is_active",
                     "created_at", "updated_at"],
        "pk": "id",
    },
]

SEQUENCES = {
    "users": "users_id_seq",
    "patents": "patents_id_seq",
    "model_providers": "model_providers_id_seq",
    "api_keys": "api_keys_id_seq",
    "notifications": "notifications_id_seq",
    "knowledge_docs": "knowledge_docs_id_seq",
}


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def col_list(columns, table):
    """Build comma-separated column list, handling schema differences."""
    return ", ".join(columns)


def placeholders(columns):
    return ", ".join("%s" for _ in columns)


def connect_sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def connect_pg():
    return psycopg2.connect(PG_URL)


def clear_pg_table(pg_conn, table_name):
    """Truncate PG table (cascading)."""
    with pg_conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
    logger.info(f"  ✓ Truncated {table_name}")


def read_sqlite_table(sqlite_conn, table_def):
    """Read all rows from SQLite."""
    columns = table_def["columns"]
    name = table_def["name"]
    # For 'models', exclude 'id' column from SQLite
    if name == "models":
        sql = "SELECT provider_id, model_id, name, capabilities, endpoint_types, context_window, max_output_tokens, max_input_tokens, model_group, is_enabled, metadata FROM models"
    else:
        sql = f"SELECT {col_list(columns, name)} FROM {name}"
    try:
        rows = sqlite_conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"  ! {name}: {e}")
        return []


def migrate_table(pg_conn, table_def, rows):
    """Insert rows into PG."""
    if not rows:
        logger.info(f"  - {table_def['name']}: 0 rows, skipped")
        return

    name = table_def["name"]
    columns = table_def["columns"]
    cols = col_list(columns, name)
    phs = placeholders(columns)
    on_conflict = "ON CONFLICT DO NOTHING"

    # Build column values, handling special types
    pg_rows = []
    for row in rows:
        vals = []
        for c in columns:
            val = row.get(c)
            # Handle JSON fields (SQLite stores as text, PG as json)
            if c in ("models",) and val is not None:
                if isinstance(val, str):
                    try:
                        json.loads(val)  # validate
                    except json.JSONDecodeError:
                        val = json.dumps(val)
            # Handle binary content in knowledge_docs
            if c == "content" and isinstance(val, bytes):
                # Try to decode as utf-8, fallback to latin-1
                try:
                    val = val.decode("utf-8")
                except UnicodeDecodeError:
                    val = val.decode("latin-1")
            # Strip NUL bytes that PG cannot handle
            if isinstance(val, str):
                val = val.replace("\x00", "")
            vals.append(val)
        pg_rows.append(vals)

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            f"INSERT INTO {name} ({cols}) VALUES %s {on_conflict}",
            pg_rows,
            template=f"({phs})",
        )
    logger.info(f"  ✓ {name}: {len(pg_rows)} rows")


def reset_sequences(pg_conn):
    """Reset sequences to max(id) + 1 for tables with auto-increment."""
    for table, seq in SEQUENCES.items():
        try:
            with pg_conn.cursor() as cur:
                cur.execute(f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
                logger.info(f"  ✓ Sequence {seq} reset")
        except Exception as e:
            logger.warning(f"  ! Sequence {seq}: {e}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    logger.info(f"SQLite: {SQLITE_PATH}")
    logger.info(f"PG:     {PG_URL[:50]}...")
    logger.info("")

    sqlite_conn = connect_sqlite()
    pg_conn = connect_pg()

    try:
        # 1. Clear PG tables in reverse dependency order
        logger.info("── 清理 PG 现有数据 ──")
        clear_order = list(reversed(TABLES))
        for t in clear_order:
            clear_pg_table(pg_conn, t["name"])
        pg_conn.commit()
        logger.info("")

        # 2. Read from SQLite and write to PG
        logger.info("── 迁移数据 ──")
        for t in TABLES:
            rows = read_sqlite_table(sqlite_conn, t)
            migrate_table(pg_conn, t, rows)
        pg_conn.commit()
        logger.info("")

        # 3. Reset sequences
        logger.info("── 重置序列 ──")
        reset_sequences(pg_conn)
        pg_conn.commit()
        logger.info("")

        # 4. Verify
        logger.info("── 校验 ──")
        verify_pg(pg_conn)
        logger.info("")
        logger.info("✅ 迁移完成")

    except Exception:
        pg_conn.rollback()
        logger.exception("❌ 迁移失败，已回滚")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()


def verify_pg(pg_conn):
    with pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        for t in TABLES:
            name = t["name"]
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {name}")
            row = cur.fetchone()
            logger.info(f"  {name}: {row['cnt']} rows")


if __name__ == "__main__":
    main()
