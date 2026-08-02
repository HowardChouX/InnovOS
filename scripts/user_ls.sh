#!/usr/bin/env bash
# 列出所有已注册用户。
# 用法：make user-ls
set -euo pipefail

# ── 数据库连接参数（可由环境变量覆盖，make 会传入）──
# 连接模式：PG_HOST 非空 → TCP（Docker 部署）；否则 → Unix socket（本地 make dev）
PG_SOCKET_DIR="${PG_SOCKET_DIR:-/tmp}"
PG_PORT="${PG_PORT:-5432}"
PG_HOST="${PG_HOST:-}"

# 从 .env 读取凭据（不 source 整个文件，避免 JSON 数组值破坏 shell）
# grep 匹配不到时返回非零，用 || true 兜底（set -e 下否则中断）
ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  PG_PASSWORD="$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  PG_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  PG_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
fi
PG_USER="${PG_USER:-innovos}"
PG_DB="${PG_DB:-innovos}"

export PGPASSWORD="${PG_PASSWORD:-}"

# TCP（Docker）用 -h <host>；Unix socket（本地）用 -h <socket_dir>
PG_HOST_ARG="${PG_HOST:-$PG_SOCKET_DIR}"

# ── 前置检查 ──
if ! command -v psql >/dev/null 2>&1; then
  echo "❌ 未找到 psql，请先安装 PostgreSQL 客户端。" >&2
  exit 1
fi
if ! pg_isready -h "$PG_HOST_ARG" -p "$PG_PORT" -q 2>/dev/null; then
  echo "❌ 无法连接数据库（$PG_HOST_ARG:$PG_PORT）。" >&2
  if [[ -z "$PG_HOST" ]]; then
    echo "   本地模式：请先启动 make start-db" >&2
  else
    echo "   Docker 模式：请确认 postgres 容器已启动（docker compose ps）" >&2
  fi
  exit 1
fi

# ── 列出用户（带表头的格式化输出）──
psql -h "$PG_HOST_ARG" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c "
  SELECT
    id,
    COALESCE(NULLIF(username, ''), '-') AS username,
    phone,
    CASE WHEN is_superuser THEN '管理员' ELSE '普通用户' END AS role,
    CASE WHEN is_active    THEN '启用'   ELSE '禁用'   END AS status,
    COALESCE(email, '-') AS email
  FROM users
  ORDER BY id;
"
