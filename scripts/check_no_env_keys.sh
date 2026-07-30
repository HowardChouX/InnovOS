#!/usr/bin/env bash
# scripts/check_no_env_keys.sh
#
# 静态检查:确保 backend/app 中没有 AI_*_API_KEY 业务读取(只允许注释历史)。
# 用于 CI / 手动回归,防止环境变量 Key 路径复活。
#
# 退出码:0=通过,1=失败

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_DIR="$REPO_ROOT/backend/app"
EXCLUDE_PATTERN="(test_|//.*AI_)"

echo "=== Checking for AI_*_API_KEY business usage in $TARGET_DIR ==="

# 查找所有 AI_xxx_API_KEY 字符串,排除注释和测试
matches=$(grep -rn "AI_[A-Z_]*_API_KEY" "$TARGET_DIR" \
    --include="*.py" \
    | grep -v "^[^:]*:[^:]*:\s*#" \
    | grep -v "test_" \
    | grep -v "\.pyc" \
    || true)

if [ -n "$matches" ]; then
    echo ""
    echo "FAIL: Found AI_*_API_KEY references in business code:"
    echo "$matches"
    echo ""
    echo "API Keys must come from api_keys table (encrypted), not env vars."
    echo "Use INNOVOS_ENCRYPT_KEY for the master encryption key only."
    exit 1
fi

echo "PASS: No AI_*_API_KEY business usage found"
exit 0