#!/usr/bin/env bash
# 将已注册用户提升为超级用户（管理员）。
# 用法：make add-admin  （交互式输入手机号）
#
# 仅能提升已注册的账户；未注册的手机号会报错退出。
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
PSQL=(psql -h "$PG_HOST_ARG" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -tA)

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

# ── 输入手机号 ──
read -rp "请输入要提升为管理员的手机号: " phone
phone="$(echo "$phone" | tr -d '[:space:]')"

if [[ ! "$phone" =~ ^1[0-9]{10}$ ]]; then
  echo "❌ 手机号格式无效（需 11 位、1 开头）。" >&2
  exit 1
fi

# ── 查询用户（参数化，防注入）──
row="$("${PSQL[@]}" -c "SELECT id || '|' || COALESCE(username,'') || '|' || is_superuser FROM users WHERE phone = '$phone' LIMIT 1")"

if [[ -z "$row" ]]; then
  echo "❌ 未找到手机号为 $phone 的已注册用户。请先注册该账户。" >&2
  exit 1
fi

IFS='|' read -r uid uname is_super <<<"$row"

if [[ "$is_super" == "t" || "$is_super" == "true" ]]; then
  echo "ℹ️  用户 $uname (id=$uid) 已经是管理员，无需操作。"
  exit 0
fi

# ── 提升 ──
"${PSQL[@]}" -c "UPDATE users SET is_superuser = TRUE WHERE id = $uid" >/dev/null

echo "✅ 已将用户 $uname (id=$uid, phone=$phone) 提升为管理员。"
