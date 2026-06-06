#!/bin/bash
# InnovOS 测试运行脚本

set -e

echo "=== InnovOS 测试 ==="

# 后端测试
echo ""
echo "--- 后端测试 ---"
cd backend
if command -v pytest &> /dev/null; then
    pytest tests/ -v --tb=short 2>&1 | head -50
else
    echo "⚠️  pytest 未安装，跳过后端测试"
    echo "   安装: pip install pytest pytest-cov httpx"
fi
cd ..

# 前端测试
echo ""
echo "--- 前端测试 ---"
cd frontend
if npm run test -- --run &> /dev/null 2>&1; then
    npm run test -- --run 2>&1 | head -50
else
    echo "⚠️  前端测试未配置或失败"
fi
cd ..

echo ""
echo "=== 测试完成 ==="
