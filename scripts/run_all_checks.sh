#!/usr/bin/env bash
# scripts/run_all_checks.sh
#
# 一次性跑完所有静态检查 / 类型检查 / 单元测试。
# CI 可直接调用此脚本。

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== 1) Backend: AI_*_API_KEY 业务代码残留 ==="
bash "$REPO_ROOT/scripts/check_no_env_keys.sh"

echo ""
echo "=== 2) Backend: OpenAI( 构造点 ==="
bash "$REPO_ROOT/scripts/check_openai_constructors.sh"

echo ""
echo "=== 3) Backend: Python 类型检查 (mypy / 暂跳过;用 pytest 兜底) ==="
# uv run mypy backend/app || echo "mypy not configured, skipping"

echo ""
echo "=== 4) Backend: 单元测试 ==="
cd "$REPO_ROOT/backend"
uv run pytest \
    tests/test_key_crypto.py \
    tests/test_schema_migration.py \
    tests/test_api_key_service.py \
    tests/test_admin_api_keys.py \
    tests/test_model_resolver_purpose.py \
    tests/test_chat_completion_unified.py \
    tests/test_ai_client_registry.py \
    tests/test_ai_base_runtime.py \
    tests/test_rotate_api_key_master.py \
    -v

echo ""
echo "=== 5) Frontend: TypeScript 检查 ==="
cd "$REPO_ROOT/frontend"
npx tsc --noEmit

echo ""
echo "=== All checks passed ==="