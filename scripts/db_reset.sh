#!/usr/bin/env bash
# 重置数据库：清空 public schema，后端重启时自动重建所有表。
# 用法：make db-reset（本地）/ make docker-reset（Docker）
#
# ⚠️ 破坏性操作：会删除所有用户、任务、知识库等业务数据。
# 重置后无任何管理员，需重新注册账户并用 make add-admin 提升。
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

# ── 二次确认（防误删）──
echo "╔════════════════════════════════════════════════════════╗"
echo "║  ⚠️  即将重置数据库：$PG_DB"
echo "║  将删除所有用户、任务、知识库、专利等业务数据。"
echo "║  重置后无管理员，需重新注册并 make add-admin。"
echo "╚════════════════════════════════════════════════════════╝"
read -rp "确认重置？输入 yes 继续，其他任意键取消: " confirm
if [[ "$confirm" != "yes" ]]; then
  echo "已取消。"
  exit 0
fi

# ── 清空 schema（后端重启时自动重建）──
psql -h "$PG_HOST_ARG" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c "
  DROP SCHEMA public CASCADE;
  CREATE SCHEMA public;
"

echo "✅ 数据库已清空。请重启后端以重建所有表："
if [[ -z "$PG_HOST" ]]; then
  echo "   make stop-apps && make dev"
else
  echo "   docker compose restart backend"
fi
