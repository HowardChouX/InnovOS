.PHONY: dev test lint clean start-db

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
	@echo "=== Linting frontend ==="
	cd frontend && npm run lint
	@echo "=== Linting backend (ruff) ==="
	cd backend && uv run ruff check app/
	@echo "=== Formatting check (black) ==="
	cd backend && uv run black --check app/
	@echo "=== Import sort check (isort) ==="
	cd backend && uv run isort --check-only app/
	@echo "=== Type check (mypy) ==="
	cd backend && uv run mypy app/

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

# ──────────────────────────────────────────────
#  格式化
# ──────────────────────────────────────────────
format:
	@echo "=== Formatting frontend (prettier) ==="
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,json,css}"
	@echo "=== Formatting backend (black + isort + ruff) ==="
	cd backend && uv run ruff check --fix app/
	cd backend && uv run isort app/
	cd backend && uv run black app/

# ──────────────────────────────────────────────
#  安全扫描
# ──────────────────────────────────────────────
security:
	@echo "=== Bandit security scan ==="
	cd backend && uv run bandit -c pyproject.toml -r app/
	@echo "=== Safety dependency scan ==="
	cd backend && uv run safety check --full-report

# ──────────────────────────────────────────────
#  Pre-commit 安装
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
#  Docker 部署
# ──────────────────────────────────────────────
docker-build:
	docker compose build --parallel

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-clean:
	docker compose down -v --remove-orphans

# ──────────────────────────────────────────────
#  数据库备份
# ──────────────────────────────────────────────
db-backup:
	@bash backend/scripts/backup_db.sh

db-restore:
	@if [ -z "$(file)" ]; then echo "Usage: make db-restore file=backup.sql.gz"; exit 1; fi
	@gunzip -c $(file) | psql "$$DATABASE_URL"
	@echo "Restored from $(file)"

# ──────────────────────────────────────────────
#  安全扫描
# ──────────────────────────────────────────────
security-scan-all:
	cd backend && uv run bandit -c pyproject.toml -r app/
	cd backend && uv run safety check --full-report

# ──────────────────────────────────────────────
#  生产构建
# ──────────────────────────────────────────────
build-all: docker-build
	@echo "All Docker images built"

# ──────────────────────────────────────────────
#  Pre-commit 安装
# ──────────────────────────────────────────────
setup-hooks:
	@echo "=== Installing pre-commit hooks ==="
	cd backend && uv run pre-commit install
	@echo "=== Installing husky hooks ==="
	cd frontend && npx husky init
