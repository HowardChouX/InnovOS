.PHONY: dev backend frontend test lint clean

# 启动开发环境
dev: backend frontend

# 启动后端
backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端
frontend:
	cd frontend && npm run dev

# 运行测试
test:
	./run_tests.sh

# 代码检查
lint:
	cd frontend && npm run lint
	cd backend && python -m py_app/app --check

# 清理构建产物
clean:
	cd frontend && rm -rf dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# 安装依赖
install:
	cd backend && uv sync
	cd frontend && npm install

# 构建生产版本
build:
	cd frontend && npm run build
