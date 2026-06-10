.PHONY: dev backend frontend test lint clean start-db

# ──────────────────────────────────────────────
#  开发环境 — 一键启动全部服务
# ──────────────────────────────────────────────

# 启动所有依赖 + 前后端
dev:
	@$(MAKE) start-db
	@echo "=== Starting backend (port 8000) ==="
	@cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
	@sleep 2
	@echo "=== Starting frontend (port 5173) ==="
	@cd frontend && npm run dev

# 启动 PostgreSQL（如未运行）
start-db:
	@pg_isready -q 2>/dev/null || (echo "=== Starting PostgreSQL ===" && sudo -u postgres pg_ctl -D /var/lib/postgres/data -l /tmp/pg.log start && sleep 2)

# 停止全部服务
stop:
	@echo "=== Stopping services ==="
	@pkill -f "uvicorn app.main" 2>/dev/null; true
	@pkill -f "vite" 2>/dev/null; true
	@echo "Stopped."

# ──────────────────────────────────────────────
#  运行测试
# ──────────────────────────────────────────────
test:
	cd backend && uv run pytest tests/ -v
	cd frontend && npm test

# ──────────────────────────────────────────────
#  代码检查
# ──────────────────────────────────────────────
lint:
	cd frontend && npm run lint
	cd backend && python -m py_app/app --check

# ──────────────────────────────────────────────
#  清理
# ──────────────────────────────────────────────
clean:
	cd frontend && rm -rf dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ──────────────────────────────────────────────
#  安装
# ──────────────────────────────────────────────
install:
	cd backend && uv sync
	cd frontend && npm install

build:
	cd frontend && npm run build
