.PHONY: dev stop test lint quality format clean install build security docker-up docker-down db-backup setup-hooks

# ══════════════════════════════════════════════
#  开发环境 — 一键启动全部服务
# ══════════════════════════════════════════════

dev:
	@$(MAKE) start-db
	@echo "=== Starting backend (port 8000) ==="
	@cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
	@sleep 2
	@echo "=== Starting frontend (port 5173) ==="
	@cd frontend && npm run dev

start-db:
	@pg_isready -q 2>/dev/null || (echo "=== Starting PostgreSQL ===" && sudo -u postgres pg_ctl -D /var/lib/postgres/data -l /tmp/pg.log start && sleep 2)

stop:
	@echo "=== Stopping services ==="
	@pkill -f "uvicorn app.main" 2>/dev/null; true
	@pkill -f "vite" 2>/dev/null; true
	@echo "Stopped."

# ══════════════════════════════════════════════
#  代码质量门禁（提交前运行）
#  make quality  =  lint + type-check + test + build + security
# ══════════════════════════════════════════════

quality:
	@echo "╔══════════════════════════════════════════╗"
	@echo "║     InnovOS 全量代码质量门禁              ║"
	@echo "╚══════════════════════════════════════════╝"
	@$(MAKE) lint
	@$(MAKE) typecheck
	@$(MAKE) test
	@$(MAKE) build
	@$(MAKE) security
	@echo ""
	@echo "✅ 质量门禁全部通过"

# ── 代码检查 ─────────────────────────────────
lint:
	@echo "=== [1/6] Frontend ESLint ==="
	cd frontend && npm run lint
	@echo "=== [2/6] Backend Ruff ==="
	cd backend && uv run ruff check app/
	@echo "=== [3/6] Backend Ruff format check ==="
	cd backend && uv run ruff format --check app/
	@echo "=== Prettier check ==="
	cd frontend && npx prettier --check "src/**/*.{ts,tsx,json,css}"

# ── 类型检查 ─────────────────────────────────
typecheck:
	@echo "=== Frontend TypeScript ==="
	cd frontend && npx tsc --noEmit
	@echo "=== Backend mypy ==="
	cd backend && uv run mypy app/

# ── 测试（带覆盖率） ──────────────────────────
test:
	@echo "=== Backend tests (coverage ≥ 60%) ==="
	cd backend && uv run pytest tests/ -v --cov=app --cov-report=term --cov-fail-under=60
	@echo "=== Frontend tests ==="
	cd frontend && npm test

# ── 构建 ──────────────────────────────────────
build:
	@echo "=== Frontend production build ==="
	cd frontend && npm run build

# ── 安全扫描 ─────────────────────────────────
security:
	@echo "=== Bandit ==="
	cd backend && uv run bandit -c pyproject.toml -r app/ -q
	@echo "=== npm audit ==="
	cd frontend && npm audit --audit-level=high 2>/dev/null

# ══════════════════════════════════════════════
#  格式化
# ══════════════════════════════════════════════

format:
	@echo "=== Frontend (prettier) ==="
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,json,css}"
	@echo "=== Backend (ruff) ==="
	cd backend && uv run ruff check --fix app/ && uv run ruff format app/

# ══════════════════════════════════════════════
#  清理
# ══════════════════════════════════════════════

clean:
	cd frontend && rm -rf dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ══════════════════════════════════════════════
#  安装
# ══════════════════════════════════════════════

install:
	cd backend && uv sync
	cd frontend && npm install

# ══════════════════════════════════════════════
#  Docker 部署
# ══════════════════════════════════════════════

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

# ══════════════════════════════════════════════
#  数据库
# ══════════════════════════════════════════════

db-backup:
	@uv run python -c "import asyncio; from app.services.backup_service import backup_service; asyncio.run(backup_service.run_now())"

db-restore:
	@if [ -z "$(file)" ]; then echo "Usage: make db-restore file=backup.sql.gz"; exit 1; fi
	@gunzip -c $(file) | psql "$$DATABASE_URL"
	@echo "Restored from $(file)"

# ══════════════════════════════════════════════
#  钩子安装
# ══════════════════════════════════════════════

setup-hooks:
	@echo "=== Installing husky hooks ==="
	cd frontend && npx husky init

# ══════════════════════════════════════════════
#  CI 模拟（在本地运行 CI 的全部检查）
# ══════════════════════════════════════════════

ci-local:
	@$(MAKE) lint
	@$(MAKE) typecheck
	@cd backend && uv run pytest tests/ -v --cov=app --cov-report=xml --cov-fail-under=60
	@cd frontend && npm test -- --coverage
	@cd backend && uv run bandit -c pyproject.toml -r app/
	@$(MAKE) build
	@echo "✅ CI checks passed locally"
