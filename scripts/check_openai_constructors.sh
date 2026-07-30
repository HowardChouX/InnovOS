#!/usr/bin/env bash
# scripts/check_openai_constructors.sh
#
# 静态检查:确保 backend/app 内 `OpenAI(` 构造只出现在
# app/algorithm/clients/openai_compatible.py(唯一封装点)。
# 用于 CI / 手动回归,防止其他地方重新直接构造 OpenAI client 绕过统一 adapter。
#
# 退出码:0=通过,1=失败

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_DIR="$REPO_ROOT/backend/app"
ALLOWED_FILES=(
    "app/algorithm/clients/openai_compatible.py"  # 唯一生产构造点
    "app/algorithm/base.py"                        # AIBase 旧形式(deprecated)
)

echo "=== Checking OpenAI( constructor usages in $TARGET_DIR ==="

# 找所有 OpenAI( 引用
matches=$(grep -rn "OpenAI(" "$TARGET_DIR" \
    --include="*.py" \
    | grep -v "\.pyc" \
    | grep -v "from openai import" \
    | grep -v "as " \
    || true)

if [ -z "$matches" ]; then
    echo "PASS: No OpenAI( found"
    exit 0
fi

# 过滤:只允许白名单文件
violations=""
while IFS= read -r line; do
    file=$(echo "$line" | cut -d: -f1)
    rel_file=${file#$REPO_ROOT/}
    is_allowed=false
    for allowed in "${ALLOWED_FILES[@]}"; do
        if [[ "$rel_file" == *"$allowed"* ]]; then
            is_allowed=true
            break
        fi
    done
    if [ "$is_allowed" = false ]; then
        violations="$violations\n$line"
    fi
done <<< "$matches"

if [ -n "$(echo -e "$violations" | grep -v '^$')" ]; then
    echo ""
    echo "FAIL: OpenAI( found outside allowed files:"
    echo -e "$violations"
    echo ""
    echo "Allowed files:"
    for f in "${ALLOWED_FILES[@]}"; do
        echo "  - $f"
    done
    echo ""
    echo "All OpenAI client construction must go through OpenAICompatibleAdapter."
    exit 1
fi

echo "PASS: OpenAI( only in allowed files"
exit 0