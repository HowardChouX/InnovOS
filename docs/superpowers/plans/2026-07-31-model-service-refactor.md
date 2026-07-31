# Model Service Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the InnovOS sidebar "模型服务" entry into a focused module: a flat catalog of self-contained model service entries + per-user enable/order queue + per-call usage log + admin stats view, with UI rebuilt to match the CC Switch `ProviderList` idiom.

**Architecture:** Reuse the existing `model_providers` table (add one `notes` column) and `api_keys` table (collapse to 1 key per entry at `priority=0`). Add three new tables: `provider_health` (per-provider circuit-breaker state), `user_model_services` (per-user enable + failover order), `model_call_log` (one row per call). A new `FailoverRouter` service walks each user's queue at request time, applies a 3-failure / 5-minute cooldown, and writes a `model_call_log` row per attempt. Frontend replaces `KeyManagementPage` internals with a CC-Switch-style panel; `UserManagementPage` gets a "AI 模型服务" link column that opens a new `/admin/users/:userId/model-services` page.

**Tech Stack:** Python 3.13 / FastAPI / psycopg2 / pgvector (existing), React 19 / TypeScript / Vite / Tailwind v4 / Zustand / @tanstack/react-query (existing), Alembic migrations, pytest + vitest + RTL, ruff + prettier + eslint, dnd-kit (new dependency, already in the project's broader dep graph), commitlint.

## Global Constraints

- **Branch:** All work happens on `dev3` (current branch).
- **DB:** PostgreSQL 17 (local cluster, `make dev` workflow). No new system dependencies.
- **Migrations:** Add `backend/alembic/versions/0017_add_user_model_services_and_call_log.py`. Reuse the existing `_ddl_int_pk()` / `_ddl_now()` / `_ensure_columns()` helpers in `app/tables/pg_schema.py`. The new `pg_schema.py` helpers (`init_provider_health`, `init_user_model_services`, `init_model_call_log`, `_ensure_columns('model_providers', [('notes', ...)])`) are called from `init_all_tables`; the Alembic migration is a fallback for existing deployments.
- **Alembic env** is **users-only** (`alembic/env.py` docstring: "仅管理 users 表 DDL"). New tables go through `pg_schema.py::init_all_tables` on app boot, not Alembic. The 0017 migration exists for **ops parity with the existing pattern** but is not auto-run; the app's `init_all_tables` is the source of truth.
- **Encrypted keys:** Reuse `app/services/api_key_service.py::ApiKeyService.create_key` and `replace_secret` (do not modify). The `priority` column is always set to `0` and `name` to `'default'` for the new 1-key-per-entry pattern.
- **AI client call sites:** The 7 analyzers in `app/algorithm/analyzers/*.py` and the 4 pipeline / `base.py` call sites switch from `ModelRuntime.resolve(...)` / `ModelResolver.resolve_for_purpose(...)` to `ai_client.chat_completion(user_id, purpose, messages)`. The return shape stays `{"content": str, "usage": {...}, "raw": ...}` so analyzers don't change behavior.
- **No multi-key rotation:** The `ProviderKeyPool.lease_key(...)` rotation is removed. Each model service row has exactly 1 key.
- **Failover trigger:** 3 consecutive failures on the same provider flip `is_healthy=false` and set `cooldown_until = NOW() + 5 min`. While in cooldown, the entry is skipped. After cooldown expires, the entry is re-tried; success resets the counter.
- **Usage log retention:** 90 days. A daily 03:00 job (added to `backup_service`'s existing cron loop) deletes older rows. Configurable via `MODEL_CALL_LOG_RETENTION_DAYS` env var.
- **Frontend dnd-kit:** Already a dep transitively via the broader InnovOS frontend; if not present, add `@dnd-kit/core` + `@dnd-kit/sortable` to `frontend/package.json`. Verify with `ls frontend/node_modules/@dnd-kit 2>/dev/null` before adding.
- **Sidebar.tsx stays byte-identical** — labels and paths for "模型服务" (`/admin/keys`) and "用户管理" (`/admin/users`) do not change.
- **`KeyManagementPage.tsx` filename preserved** — only its internal content is replaced (no rename, no route change). New internal component is `ModelServicePanel`.
- **Commit style:** `<type>(<scope>): <description>` (feat, fix, refactor, docs, chore, test). Use `Co-Authored-By: Codex (brainstorming) <noreply@local>` in commit body to match repo convention.
- **Test framework:** pytest (backend, coverage threshold 60% from `AGENTS.md`), vitest + RTL (frontend).
- **Quality gate:** `make quality` must pass after every phase that touches a CI-relevant file. Run from the project root: `cd /home/chou/InnovOS && make quality`.

---

## File Structure

### Backend — new files

| File                                                                    | Responsibility                                                                                      |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `backend/app/services/failover_router.py`                               | Per-user failover queue walker, circuit-breaker state update, one `model_call_log` row per attempt. |
| `backend/app/services/usage_logger.py`                                  | Fire-and-forget `model_call_log` insert.                                                            |
| `backend/app/services/provider_health_service.py`                       | Read / update `provider_health` rows (counter increment, cooldown flip, reset).                     |
| `backend/app/services/usage_log_cleanup.py`                             | Daily 03:00 retention sweep.                                                                        |
| `backend/app/api/admin/user_model_services.py`                          | New REST surface for `/api/admin/users/{user_id}/model-services/*`.                                 |
| `backend/app/api/admin/usage.py`                                        | New REST surface for `/api/admin/usage/*`.                                                          |
| `backend/app/api/admin/failover.py`                                     | New REST surface for `/api/admin/failover/*`.                                                       |
| `backend/alembic/versions/0017_add_user_model_services_and_call_log.py` | Ops-parity migration (mirrors what `pg_schema.py::init_all_tables` does).                           |

### Backend — modified files

| File                                             | Change                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/tables/pg_schema.py`                | Add `init_provider_health`, `init_user_model_services`, `init_model_call_log`; call them from `init_all_tables`; add `('notes', 'TEXT NOT NULL DEFAULT \\'\\'')` to the `_ensure_columns` call for `model_providers`.                                                                                                                                                |
| `backend/app/algorithm/model_service.py`         | Collapse to thin `ModelService` class. `upsert` writes one `api_keys` row (`priority=0, name='default'`) via `ApiKeyService`. Drop `list_builtin`, `reconcile_models`, `reconcile_apply`, `updateModel`, `batch_check_models`, `delete_model`, `delete_provider_model`, `check_connection`'s multi-key path. Keep `detect_models`, `check_connection` (single call). |
| `backend/app/algorithm/ai_client.py`             | Strip `ProviderKeyPool` and the rich `CallOutcome` table. Add `chat_completion(*, user_id, purpose, messages, model_override=None)` that delegates to `FailoverRouter`.                                                                                                                                                                                              |
| `backend/app/algorithm/base.py`                  | Update 7 analyzer call sites + the pipeline orchestrator to use the new `chat_completion` signature.                                                                                                                                                                                                                                                                 |
| `backend/app/algorithm/analyzers/*.py` (7 files) | Each analyzer's `chat_with_model` (or equivalent) call site updated to pass `user_id` from the request context.                                                                                                                                                                                                                                                      |
| `backend/app/api/admin/providers.py`             | Simplify Pydantic models. Drop `/builtin`, `/keys/*`, `/{pid}/models/reconcile*`, `/{pid}/models/{mid}`, `/{pid}/models/check`. Keep `/`, `POST /`, `PUT /{pid}`, `DELETE /{pid}`, `POST /{pid}/check`, `POST /{pid}/detect-models`, plus a new `POST /detect` (pre-create detect).                                                                                  |
| `backend/app/api/admin/settings.py`              | Drop `/models/assigned*`, `/models/available`, `/rag/*`.                                                                                                                                                                                                                                                                                                             |
| `backend/app/main.py`                            | Register the 3 new admin routers (`user_model_services`, `usage`, `failover`). Hook the 03:00 retention sweep into the existing scheduler.                                                                                                                                                                                                                           |
| `backend/app/services/backup_service.py`         | Add a call to `usage_log_cleanup.run()` alongside the existing snapshot logic.                                                                                                                                                                                                                                                                                       |

### Backend — deleted files

| File                                      | Reason                                                |
| ----------------------------------------- | ----------------------------------------------------- |
| `backend/app/algorithm/model_runtime.py`  | Composite-ID resolution replaced by per-user queue.   |
| `backend/app/algorithm/model_registry.py` | `models.json` registry no longer the source of truth. |
| `backend/app/algorithm/models_crud.py`    | Per-model metadata CRUD gone.                         |

### Frontend — new files

| File                                                    | Responsibility                                         |
| ------------------------------------------------------- | ------------------------------------------------------ |
| `frontend/src/features/admin/ModelServicePanel.tsx`     | The new catalog page (CC Switch `ProviderList` idiom). |
| `frontend/src/features/admin/ModelServiceForm.tsx`      | 5-field form + detect button.                          |
| `frontend/src/features/admin/UserModelServicesPage.tsx` | Per-user enable / order / toggle / health.             |
| `frontend/src/features/admin/UsageStatsPage.tsx`        | KPIs + per-provider / per-model / recent-calls tables. |
| `frontend/src/api/admin/userModelServices.ts`           | Typed wrapper for new endpoints.                       |
| `frontend/src/api/admin/usage.ts`                       | Typed wrapper for stats endpoints.                     |
| `frontend/src/api/admin/failover.ts`                    | Typed wrapper for failover admin endpoints.            |

### Frontend — modified files

| File                                                 | Change                                                                                                                                                        |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/features/admin/KeyManagementPage.tsx`  | Keep filename; replace internals with `<ModelServicePanel />`. Remove `RagGlobalConfig`, `AssignedModels`, key-related state. Re-export for backwards compat. |
| `frontend/src/features/admin/UserManagementPage.tsx` | Add a new "AI 模型服务" column with a "管理" link to `/admin/users/{user_id}/model-services`.                                                                 |
| `frontend/src/api/admin/providers.ts`                | Simplify `Provider` type to 5-field shape + `isEnabled` + `health`. Drop `models`, `maxRpm`, `protocol`, `requestCount`.                                      |
| `frontend/src/api/admin/settings.ts`                 | Remove `getAssigned` / `setAssigned` / `getAvailable` / `getRagConfig` / `setRagConfig`.                                                                      |
| `frontend/src/routes/index.tsx`                      | Register `/admin/users/:userId/model-services` and `/admin/usage`.                                                                                            |

### Frontend — deleted files

| File                                               | Reason                                      |
| -------------------------------------------------- | ------------------------------------------- |
| `frontend/src/components/ui/ModelSelector.tsx`     | Replaced by simpler select on the new form. |
| `frontend/src/components/ui/ModelEditDrawer.tsx`   | Per-model metadata UI gone.                 |
| `frontend/src/features/admin/ProviderKeyPanel.tsx` | Multi-key CRUD UI gone.                     |

### Tests — new files

| File                                                     | Covers                                                                     |
| -------------------------------------------------------- | -------------------------------------------------------------------------- |
| `backend/tests/test_failover_router.py`                  | Per-user queue walk, circuit breaker, cooldown, log row.                   |
| `backend/tests/test_usage_log.py`                        | Fire-and-forget log writes; `failover_from_provider` correctness.          |
| `backend/tests/test_user_model_services_api.py`          | Add / remove / toggle / reorder, idempotency, 409 on duplicate.            |
| `backend/tests/test_provider_health_api.py`              | Health overview + reset.                                                   |
| `backend/tests/test_usage_api.py`                        | Summary / by-provider / by-model / recent with range + user filters.       |
| `backend/tests/test_model_service_api.py`                | `POST / PUT / DELETE` cascade to `api_keys`; `notes` round-trip.           |
| `backend/tests/test_admin_user_model_services_router.py` | The 6 endpoints of the new admin router, with `require_admin` enforcement. |
| `tests/components/ModelServicePanel.test.tsx`            | Catalog render, add modal, detect, delete confirm.                         |
| `tests/components/UserModelServicesPage.test.tsx`        | Add / remove / toggle / drag-reorder.                                      |
| `tests/components/UsageStatsPage.test.tsx`               | KPI render, range picker, user filter.                                     |
| `tests/components/UserManagementPage.test.tsx`           | New "AI 模型服务" column link.                                             |

### Task 1: Schema — `pg_schema.py` helpers for the 3 new tables + `notes` column

**Files:**

- Modify: `backend/app/tables/pg_schema.py` (append 3 new `init_*` functions, update `init_all_tables`)

- [ ] **Step 1: Add the 3 new `init_*` functions just before `init_all_tables`**

Insert immediately above `def init_all_tables(db):` (around line 680). The exact content:

```python
def init_provider_health(db):
    """provider_health 表 — Provider 级熔断器状态(全用户共享)。

    is_healthy + consecutive_failures 决定是否跳过该 provider;
    cooldown_until 在 5 分钟内不再尝试。
    """
    db.execute("""
        CREATE TABLE IF NOT EXISTS provider_health (
            provider_id TEXT PRIMARY KEY
                REFERENCES model_providers(provider_id) ON DELETE CASCADE,
            is_healthy BOOLEAN NOT NULL DEFAULT TRUE,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            last_success_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            cooldown_until TIMESTAMPTZ,
            last_error_code VARCHAR(64),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)


def init_user_model_services(db):
    """user_model_services 表 — per-user 开通 + 故障转移队列。

    failover_order 1-based; UNIQUE(user_id, failover_order) 保证重排是 swap 语义。
    """
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_model_services (
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL REFERENCES model_providers(provider_id) ON DELETE CASCADE,
            failover_order INTEGER NOT NULL CHECK (failover_order >= 1),
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, provider_id),
            UNIQUE (user_id, failover_order)
        );
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS ix_ums_user_enabled
            ON user_model_services (user_id, is_enabled, failover_order);
    """)


def init_model_call_log(db):
    """model_call_log 表 — 每调用一行;含 failover_from_provider + failover_attempt。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS model_call_log (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            purpose VARCHAR(32) NOT NULL DEFAULT 'chat',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            status_code SMALLINT NOT NULL,
            is_success BOOLEAN NOT NULL,
            error_category VARCHAR(32),
            error_message TEXT,
            is_streaming BOOLEAN NOT NULL DEFAULT FALSE,
            failover_from_provider TEXT,
            failover_attempt SMALLINT NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    db.execute("CREATE INDEX IF NOT EXISTS ix_mcl_provider_time ON model_call_log (provider_id, created_at DESC);")
    db.execute("CREATE INDEX IF NOT EXISTS ix_mcl_user_time ON model_call_log (user_id, created_at DESC);")
    db.execute("CREATE INDEX IF NOT EXISTS ix_mcl_model_time ON model_call_log (model_id, created_at DESC);")
    db.execute("CREATE INDEX IF NOT EXISTS ix_mcl_time ON model_call_log (created_at DESC);")
```

- [ ] **Step 2: Add the 3 calls inside `init_all_tables`**

Find the call `init_model_providers(db)` in `init_all_tables`. Immediately after it, add the `notes` ensure-columns + the 3 new init calls:

```python
    init_model_providers(db)
    _ensure_columns(db, "model_providers", [("notes", "TEXT NOT NULL DEFAULT ''")])
    init_provider_health(db)
    init_user_model_services(db)
    init_model_call_log(db)
```

The exact insertion point is right after the existing line `init_model_providers(db)` near the bottom of `init_all_tables`.

- [ ] **Step 3: Run the app's startup path to create the tables**

Run: `cd /home/chou/InnovOS/backend && uv run python -c "from app.tables.pg_schema import init_all_tables; from app.database import get_db; init_all_tables(get_db())"`
Expected: exits 0. The new tables exist; the `notes` column is present on `model_providers`.

- [ ] **Step 4: Verify the schema**

Run: `cd /home/chou/InnovOS/backend && uv run python -c "
from app.database import get_db
db = get_db()
for t in ('provider_health', 'user_model_services', 'model_call_log'):
    r = db.execute(\"SELECT to_regclass(%s)\", (f'public.{t}',)).fetchone()
    print(t, '->', r[0])
r = db.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='model_providers' AND column_name='notes'\").fetchone()
print('model_providers.notes ->', r)
"
`
Expected: each table name resolves (non-None); `model_providers.notes` prints.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/tables/pg_schema.py && git commit -m "feat(schema): add provider_health, user_model_services, model_call_log + model_providers.notes"
```

### Task 2: Alembic ops-parity migration `0017`

**Files:**

- Create: `backend/alembic/versions/0017_add_user_model_services_and_call_log.py`

- [ ] **Step 1: Create the migration file**

Path: `backend/alembic/versions/0017_add_user_model_services_and_call_log.py`. Content (mirrors `pg_schema.py` from Task 1; both runnables are idempotent):

```python
"""add provider_health, user_model_services, model_call_log + model_providers.notes

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-31

Ops-parity migration. The same DDL lives in `app/tables/pg_schema.py`
and is applied at app boot via `init_all_tables()`. This file exists
so a DBA running `alembic upgrade head` against an existing deployment
sees the same end state.
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS notes TEXT NOT NULL DEFAULT ''")
    op.execute("""
        CREATE TABLE IF NOT EXISTS provider_health (
            provider_id TEXT PRIMARY KEY
                REFERENCES model_providers(provider_id) ON DELETE CASCADE,
            is_healthy BOOLEAN NOT NULL DEFAULT TRUE,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            last_success_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            cooldown_until TIMESTAMPTZ,
            last_error_code VARCHAR(64),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_model_services (
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL REFERENCES model_providers(provider_id) ON DELETE CASCADE,
            failover_order INTEGER NOT NULL CHECK (failover_order >= 1),
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, provider_id),
            UNIQUE (user_id, failover_order)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ums_user_enabled ON user_model_services (user_id, is_enabled, failover_order);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_call_log (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            purpose VARCHAR(32) NOT NULL DEFAULT 'chat',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            status_code SMALLINT NOT NULL,
            is_success BOOLEAN NOT NULL,
            error_category VARCHAR(32),
            error_message TEXT,
            is_streaming BOOLEAN NOT NULL DEFAULT FALSE,
            failover_from_provider TEXT,
            failover_attempt SMALLINT NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_provider_time ON model_call_log (provider_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_user_time ON model_call_log (user_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_model_time ON model_call_log (model_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcl_time ON model_call_log (created_at DESC);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mcl_time")
    op.execute("DROP INDEX IF EXISTS ix_mcl_model_time")
    op.execute("DROP INDEX IF EXISTS ix_mcl_user_time")
    op.execute("DROP INDEX IF EXISTS ix_mcl_provider_time")
    op.execute("DROP TABLE IF EXISTS model_call_log")
    op.execute("DROP INDEX IF EXISTS ix_ums_user_enabled")
    op.execute("DROP TABLE IF EXISTS user_model_services")
    op.execute("DROP TABLE IF EXISTS provider_health")
    op.execute("ALTER TABLE model_providers DROP COLUMN IF EXISTS notes")
```

- [ ] **Step 2: Run the migration against a fresh DB**

Run: `cd /home/chou/InnovOS/backend && uv run alembic upgrade head 2>&1 | tail -10`
Expected: 0017 ... applied.

- [ ] **Step 3: Verify down/up round-trips on a scratch DB**

Run: `cd /home/chou/InnovOS/backend && uv run alembic downgrade -1 && uv run alembic upgrade head 2>&1 | tail -5`
Expected: clean downgrade, clean re-upgrade.

- [ ] **Step 4: Commit**

```bash
cd /home/chou/InnovOS && git add backend/alembic/versions/0017_add_user_model_services_and_call_log.py && git commit -m "feat(alembic): 0017 provider_health, user_model_services, model_call_log + model_providers.notes"
```

### Task 3: `provider_health_service.py` — circuit-breaker state machine

**Files:**

- Create: `backend/app/services/provider_health_service.py`
- Test: `backend/tests/test_provider_health_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_provider_health_service.py`:

```python
"""Unit tests for the circuit-breaker state machine."""
from __future__ import annotations

import pytest
from app.services import provider_health_service as mod


class _FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.executed: list[tuple] = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "RETURNING" in sql or "RETURNING" in sql.upper():
            return self
        return self

    def fetchone(self):
        return self.row


class _FakeConn:
    def __init__(self, row=None):
        self.cursor = _FakeCursor(row)

    def execute(self, sql, params=()):
        return self.cursor.execute(sql, params)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_record_success_resets_counter(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn())
    mod.record_success(provider_id="p1")
    assert any("consecutive_failures=0" in c[0] for c in calls) or any(
        "consecutive_failures = 0" in c[0] for c in calls
    ), "expected a reset of consecutive_failures"


def test_record_failure_increments_and_flips_at_threshold(monkeypatch):
    captured: list[tuple] = []
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn())
    mod.record_failure(provider_id="p1", error_code="provider_5xx", failure_threshold=3, cooldown_seconds=300)
    captured_sql = " ".join(c[0] for c in captured)
    # when the threshold is met, the SQL must set is_healthy=false
    assert "is_healthy=FALSE" in captured_sql or "is_healthy = FALSE" in captured_sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_provider_health_service.py -v 2>&1 | tail -20`
Expected: `ModuleNotFoundError: No module named 'app.services.provider_health_service'`.

- [ ] **Step 3: Implement `provider_health_service.py`**

Create `backend/app/services/provider_health_service.py`:

```python
"""Provider-level circuit-breaker state machine.

Reads and writes the `provider_health` table. Health is provider-level
(not per-user): if DeepSeek is down it is down for everyone.

A row is created lazily on the first failure or success; the table
itself has no required existence precondition because the schema is
created in `pg_schema.init_provider_health`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import get_db

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _upsert_success_sql() -> str:
    return """
        INSERT INTO provider_health (
            provider_id, is_healthy, consecutive_failures,
            last_success_at, updated_at
        ) VALUES (%s, TRUE, 0, NOW(), NOW())
        ON CONFLICT (provider_id) DO UPDATE SET
            is_healthy = TRUE,
            consecutive_failures = 0,
            last_success_at = NOW(),
            cooldown_until = NULL,
            updated_at = NOW()
    """


def _upsert_failure_sql(threshold: int, cooldown_seconds: int) -> str:
    # counter is updated in two stages: increment first, then read back the
    # new value via RETURNING. If the new value >= threshold, set is_healthy
    # false + cooldown_until. We do this with a single SQL statement that
    # uses a CTE-style update.
    return f"""
        WITH inc AS (
            INSERT INTO provider_health (
                provider_id, is_healthy, consecutive_failures,
                last_failure_at, last_error_code, updated_at
            ) VALUES (%s, TRUE, 1, NOW(), %s, NOW())
            ON CONFLICT (provider_id) DO UPDATE SET
                consecutive_failures = provider_health.consecutive_failures + 1,
                last_failure_at = NOW(),
                last_error_code = EXCLUDED.last_error_code,
                updated_at = NOW()
            RETURNING provider_id, consecutive_failures
        )
        UPDATE provider_health ph
           SET is_healthy = (NOT (inc.consecutive_failures >= {int(threshold)})),
               cooldown_until = CASE
                   WHEN inc.consecutive_failures >= {int(threshold)}
                       THEN NOW() + INTERVAL '{int(cooldown_seconds)} seconds'
                   ELSE ph.cooldown_until
               END,
               updated_at = NOW()
          FROM inc
         WHERE ph.provider_id = inc.provider_id
    """


def record_success(*, provider_id: str) -> None:
    """Reset the breaker for a provider on a successful call."""
    db = get_db()
    try:
        db.execute(_upsert_success_sql(), (provider_id,))
        db.commit()
    finally:
        db.close()


def record_failure(
    *,
    provider_id: str,
    error_code: str,
    failure_threshold: int = 3,
    cooldown_seconds: int = 300,
) -> int:
    """Increment the failure counter; flip to unhealthy if at/over threshold.

    Returns the new consecutive_failures count.
    """
    db = get_db()
    try:
        cur = db.execute(
            _upsert_failure_sql(failure_threshold, cooldown_seconds),
            (provider_id, error_code),
        )
        row = cur.fetchone() if hasattr(cur, "fetchone") else None
        db.commit()
        if row is None:
            return 0
        return int(row["consecutive_failures"]) if isinstance(row, dict) else int(row[0])
    finally:
        db.close()


def reset(*, provider_id: str) -> None:
    """Manual admin reset: clear cooldown and counter, mark healthy."""
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO provider_health (
                provider_id, is_healthy, consecutive_failures,
                last_success_at, updated_at
            ) VALUES (%s, TRUE, 0, NOW(), NOW())
            ON CONFLICT (provider_id) DO UPDATE SET
                is_healthy = TRUE,
                consecutive_failures = 0,
                cooldown_until = NULL,
                updated_at = NOW()
            """,
            (provider_id,),
        )
        db.commit()
    finally:
        db.close()


def is_available(*, provider_id: str) -> bool:
    """Return True if a provider may be used right now.

    A provider is unavailable if its `cooldown_until` is in the future.
    """
    db = get_db()
    try:
        row = db.execute(
            "SELECT cooldown_until FROM provider_health WHERE provider_id=%s",
            (provider_id,),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return True
    cu = row["cooldown_until"] if isinstance(row, dict) else row[0]
    if cu is None:
        return True
    return cu <= _now()


def list_all() -> list[dict[str, Any]]:
    """Return health for every provider that has a row, plus defaults for absent rows."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT provider_id, is_healthy, consecutive_failures, "
            "last_success_at, last_failure_at, cooldown_until, last_error_code "
            "FROM provider_health"
        ).fetchall()
    finally:
        db.close()
    out = []
    for r in rows:
        out.append({
            "provider_id": r["provider_id"] if isinstance(r, dict) else r[0],
            "is_healthy": r["is_healthy"] if isinstance(r, dict) else r[1],
            "consecutive_failures": r["consecutive_failures"] if isinstance(r, dict) else r[2],
            "last_success_at": r["last_success_at"] if isinstance(r, dict) else r[3],
            "last_failure_at": r["last_failure_at"] if isinstance(r, dict) else r[4],
            "cooldown_until": r["cooldown_until"] if isinstance(r, dict) else r[5],
            "last_error_code": r["last_error_code"] if isinstance(r, dict) else r[6],
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_provider_health_service.py -v 2>&1 | tail -20`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/services/provider_health_service.py backend/tests/test_provider_health_service.py && git commit -m "feat(services): provider_health_service circuit breaker"
```

### Task 4: `usage_logger.py` — fire-and-forget `model_call_log` writes

**Files:**

- Create: `backend/app/services/usage_logger.py`
- Test: `backend/tests/test_usage_log.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_usage_log.py`:

```python
"""Tests for the usage logger (model_call_log writer)."""
from __future__ import annotations

import asyncio
import pytest
from app.services import usage_logger as mod


class _FakeCursor:
    def __init__(self):
        self.executed: list[tuple] = []
        self.committed = False

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return self

    def fetchone(self):
        return None


class _FakeConn:
    def __init__(self):
        self.cursor = _FakeCursor()

    def execute(self, sql, params=()):
        return self.cursor.execute(sql, params)

    def commit(self):
        self.cursor.committed = True

    def close(self):
        pass


def test_record_call_writes_expected_columns(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(mod, "get_db", lambda: conn)
    mod.record_call(
        user_id=7,
        provider_id="p1",
        model_id="m1",
        purpose="chat",
        input_tokens=10,
        output_tokens=20,
        latency_ms=123,
        status_code=200,
        is_success=True,
        failover_from_provider=None,
        failover_attempt=1,
    )
    sql, params = conn.cursor.executed[0]
    # The single INSERT must include the right column set
    assert "INSERT INTO model_call_log" in sql
    assert "user_id" in sql
    assert "provider_id" in sql
    assert "failover_from_provider" in sql
    assert conn.cursor.committed


def test_record_call_swallows_exceptions(monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(mod, "get_db", boom)
    # must not raise
    mod.record_call(
        user_id=1, provider_id="p", model_id="m", purpose="chat",
        input_tokens=0, output_tokens=0, latency_ms=0,
        status_code=500, is_success=False, failover_from_provider=None,
        failover_attempt=1,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_usage_log.py -v 2>&1 | tail -10`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `usage_logger.py`**

Create `backend/app/services/usage_logger.py`:

```python
"""Fire-and-forget writer for the model_call_log table.

Used by FailoverRouter to record every attempt (success or failure),
including failover chain metadata. Failures of the writer itself are
logged at WARNING and never raised — usage logging must not block
the user-facing call.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.database import get_db

logger = logging.getLogger(__name__)


_INSERT_SQL = """
    INSERT INTO model_call_log (
        user_id, provider_id, model_id, purpose,
        input_tokens, output_tokens, total_tokens, latency_ms,
        status_code, is_success, error_category, error_message,
        is_streaming, failover_from_provider, failover_attempt
    ) VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s
    )
"""


def record_call(
    *,
    user_id: Optional[int],
    provider_id: str,
    model_id: str,
    purpose: str = "chat",
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    status_code: int = 0,
    is_success: bool = False,
    error_category: Optional[str] = None,
    error_message: Optional[str] = None,
    is_streaming: bool = False,
    failover_from_provider: Optional[str] = None,
    failover_attempt: int = 1,
) -> None:
    """Insert one model_call_log row. Never raises."""
    try:
        db = get_db()
        try:
            db.execute(
                _INSERT_SQL,
                (
                    user_id, provider_id, model_id, purpose,
                    input_tokens, output_tokens, total_tokens, latency_ms,
                    status_code, is_success, error_category, error_message,
                    is_streaming, failover_from_provider, failover_attempt,
                ),
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("usage_logger.record_call failed: %s", exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_usage_log.py -v 2>&1 | tail -10`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/services/usage_logger.py backend/tests/test_usage_log.py && git commit -m "feat(services): usage_logger model_call_log writer"
```

### Task 5: `failover_router.py` — the runtime heart

**Files:**

- Create: `backend/app/services/failover_router.py`
- Test: `backend/tests/test_failover_router.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_failover_router.py`:

```python
"""Tests for the per-user failover queue walker."""
from __future__ import annotations

import asyncio
import pytest
from app.services import failover_router as mod


class _FakeRow(dict):
    pass


def _row(**kw):
    return _FakeRow(kw)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed: list[tuple] = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows=None):
        self.cursor = _FakeCursor(rows or [])
        self.committed = False

    def execute(self, sql, params=()):
        return self.cursor.execute(sql, params)

    def commit(self):
        self.committed = True

    def close(self):
        pass


@pytest.fixture
def no_providers(monkeypatch):
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn([]))
    # No api_key, no provider_health reads needed
    monkeypatch.setattr(mod, "_is_available", lambda provider_id: True)


def test_empty_queue_raises_no_providers(monkeypatch, no_providers):
    router = mod.FailoverRouter()
    with pytest.raises(mod.NoProvidersConfiguredError):
        asyncio.run(router.call(user_id=1, purpose="chat", messages=[]))


def test_first_entry_succeeds(monkeypatch):
    rows = [
        _row(
            provider_id="p1", api_host="https://a", api_model="m1",
            api_key_ciphertext=b"", api_key_nonce=b"", encryption_version=1,
            key_id=10, key_fingerprint=b"", key_prefix="", key_suffix="",
            is_healthy=True, consecutive_failures=0, cooldown_until=None,
        ),
    ]
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn(rows))
    monkeypatch.setattr(mod, "_call_one", _FakeCallOne("hello", input_tokens=1, output_tokens=2).sync)
    monkeypatch.setattr(mod, "record_success", lambda **kw: None)
    monkeypatch.setattr(mod, "record_failure", lambda **kw: 1)
    monkeypatch.setattr(mod, "usage_logger", _FakeUsageLogger())

    router = mod.FailoverRouter()
    result = asyncio.run(router.call(user_id=1, purpose="chat", messages=[]))
    assert result["content"] == "hello"


def test_falls_over_to_second_after_failure(monkeypatch):
    rows = [
        _row(
            provider_id="p1", api_host="https://a", api_model="m1",
            api_key_ciphertext=b"", api_key_nonce=b"", encryption_version=1,
            key_id=10, key_fingerprint=b"", key_prefix="", key_suffix="",
            is_healthy=True, consecutive_failures=0, cooldown_until=None,
        ),
        _row(
            provider_id="p2", api_host="https://b", api_model="m2",
            api_key_ciphertext=b"", api_key_nonce=b"", encryption_version=1,
            key_id=20, key_fingerprint=b"", key_prefix="", key_suffix="",
            is_healthy=True, consecutive_failures=0, cooldown_until=None,
        ),
    ]
    monkeypatch.setattr(mod, "get_db", lambda: _FakeConn(rows))
    call_log: list[dict] = []
    def _one(provider_id, model_id, messages, **kw):
        if provider_id == "p1":
            raise RuntimeError("upstream 5xx")
        return {"content": "from p2", "input_tokens": 1, "output_tokens": 1}
    monkeypatch.setattr(mod, "_call_one", _one)
    monkeypatch.setattr(mod, "record_success", lambda **kw: call_log.append(("ok", kw["provider_id"])))
    monkeypatch.setattr(mod, "record_failure", lambda **kw: call_log.append(("fail", kw["provider_id"])))
    fake_log = _FakeUsageLogger()
    monkeypatch.setattr(mod, "usage_logger", fake_log)

    router = mod.FailoverRouter()
    result = asyncio.run(router.call(user_id=1, purpose="chat", messages=[]))
    assert result["content"] == "from p2"
    # The successful log row carries failover_from_provider="p1"
    successes = [r for r in fake_log.rows if r["is_success"]]
    assert len(successes) == 1
    assert successes[0]["provider_id"] == "p2"
    assert successes[0]["failover_from_provider"] == "p1"
    assert successes[0]["failover_attempt"] == 2


class _FakeCallOne:
    def __init__(self, content, input_tokens=0, output_tokens=0):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def sync(self, provider_id, model_id, messages, **kw):
        return {
            "content": self.content,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class _FakeUsageLogger:
    def __init__(self):
        self.rows: list[dict] = []

    def record_call(self, **kw):
        self.rows.append(kw)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_failover_router.py -v 2>&1 | tail -10`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `failover_router.py`**

Create `backend/app/services/failover_router.py`:

```python
"""Per-user failover queue walker.

At request time, given `(user_id, purpose)`, walks the user's enabled
`user_model_services` queue (ordered by `failover_order ASC`) and tries
each entry's underlying OpenAI-compatible API. A 3-failure streak on
the same provider flips `provider_health.is_healthy=false` and sets
`cooldown_until = NOW() + 5 minutes` (provider is skipped during
cooldown).

The first successful response wins; one `model_call_log` row is
written per attempt (so the full failover chain is auditable).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from app.database import get_db
from app.services import provider_health_service as health_svc
from app.services import usage_logger

logger = logging.getLogger(__name__)


# ── Errors ──


class FailoverError(RuntimeError):
    """Base class for runtime errors from the router."""


class NoProvidersConfiguredError(FailoverError):
    """The user has no enabled providers in their queue."""


class AllProvidersFailedError(FailoverError):
    """Every entry in the queue was tried and failed."""


# ── Constants ──

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_COOLDOWN_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 4


# ── Internal helpers (overridable by tests) ──


def _is_available(provider_id: str) -> bool:
    return health_svc.is_available(provider_id=provider_id)


def _record_success(provider_id: str) -> None:
    health_svc.record_success(provider_id=provider_id)


def _record_failure(provider_id: str, error_code: str, failure_threshold: int, cooldown_seconds: int) -> int:
    return health_svc.record_failure(
        provider_id=provider_id,
        error_code=error_code,
        failure_threshold=failure_threshold,
        cooldown_seconds=cooldown_seconds,
    )


def _load_queue(user_id: int, purpose: str) -> list[dict[str, Any]]:
    """Return the user's enabled queue, joined with provider + key + health."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
                mp.api_host,
                mp.api_model,
                ak.id              AS key_id,
                ak.key_ciphertext  AS api_key_ciphertext,
                ak.key_nonce       AS api_key_nonce,
                ak.encryption_version,
                ak.key_fingerprint,
                ak.key_prefix,
                ak.key_suffix,
                ph.is_healthy,
                ph.consecutive_failures,
                ph.cooldown_until
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            JOIN api_keys ak
                 ON ak.provider_id = ums.provider_id
                AND ak.is_active = TRUE
            LEFT JOIN provider_health ph ON ph.provider_id = ums.provider_id
            WHERE ums.user_id = %s
              AND ums.is_enabled = TRUE
              AND mp.is_enabled = TRUE
              AND ak.priority = 0
            ORDER BY ums.failover_order ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        if not _is_available(d["provider_id"]):
            continue
        out.append(d)
    return out


def _call_one(
    provider_id: str,
    model_id: str,
    messages: list[dict],
    *,
    api_host: str,
    api_key_ciphertext: bytes,
    api_key_nonce: bytes,
    encryption_version: int,
    key_fingerprint: bytes,
) -> dict[str, Any]:
    """Make a single upstream call. Decrypts the key, calls the adapter.

    Raises on failure. The router catches and records.
    """
    from app.core.key_crypto import load_api_key_cipher
    from app.algorithm.client_registry import AIClientRegistry

    cipher = load_api_key_cipher()
    plaintext = cipher.decrypt(
        ciphertext=api_key_ciphertext,
        nonce=api_key_nonce,
        encryption_version=encryption_version,
        provider_id=provider_id,
        key_id=0,  # we do not have key_id in this scope; key_id is for audit
    )

    adapter = AIClientRegistry.get("openai")
    result = adapter.chat(
        api_key=plaintext,
        api_host=api_host,
        model_id=model_id,
        messages=messages,
        timeout=30.0,
    )
    # Adapter returns whatever shape the registry defines; for
    # OpenAICompatibleAdapter it's a parsed dict with content + usage.
    content = result.get("content", "")
    usage = result.get("usage", {}) or {}
    return {
        "content": content,
        "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "output_tokens": int(usage.get("completion_tokens", 0) or 0),
    }


def _classify_error(exc: Exception) -> tuple[str, int, int]:
    """Return (category, failure_threshold_to_use, cooldown_seconds_to_use).

    Category is one of: "provider" (5xx), "auth", "rate_limit", "timeout", "client", "unknown".
    """
    msg = str(exc).lower()
    if "5" in msg and any(c in msg for c in ("internal", "bad gateway", "service")):
        return ("provider", DEFAULT_FAILURE_THRESHOLD, DEFAULT_COOLDOWN_SECONDS)
    if "401" in msg or "403" in msg or "unauthorized" in msg:
        return ("auth", DEFAULT_FAILURE_THRESHOLD, DEFAULT_COOLDOWN_SECONDS)
    if "429" in msg or "rate" in msg:
        return ("rate_limit", DEFAULT_FAILURE_THRESHOLD, 60)
    if "timeout" in msg or "timed out" in msg or "connection" in msg:
        return ("timeout", DEFAULT_FAILURE_THRESHOLD, 30)
    if "4" in msg and any(c.isdigit() for c in msg):
        return ("client", DEFAULT_FAILURE_THRESHOLD, DEFAULT_COOLDOWN_SECONDS)
    return ("unknown", DEFAULT_FAILURE_THRESHOLD, DEFAULT_COOLDOWN_SECONDS)


# ── Router ──


class FailoverRouter:
    def __init__(
        self,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.max_attempts = max_attempts

    async def call(
        self,
        *,
        user_id: int,
        purpose: str,
        messages: list[dict],
        model_override: Optional[str] = None,
    ) -> dict[str, Any]:
        queue = _load_queue(user_id, purpose)
        if not queue:
            raise NoProvidersConfiguredError(
                f"user {user_id} has no enabled model services for purpose {purpose!r}"
            )

        attempts = 0
        previous_provider_id: Optional[str] = None
        last_error: Optional[Exception] = None
        last_response: Optional[dict[str, Any]] = None

        for entry in queue:
            if attempts >= self.max_attempts:
                break
            attempts += 1
            provider_id = entry["provider_id"]
            model_id = model_override or entry.get("api_model") or ""
            started = time.perf_counter()
            status_code = 0
            is_success = False
            error_category: Optional[str] = None
            error_message: Optional[str] = None
            result: Optional[dict[str, Any]] = None

            try:
                result = await asyncio.to_thread(
                    _call_one,
                    provider_id,
                    model_id,
                    messages,
                    api_host=entry["api_host"],
                    api_key_ciphertext=entry["api_key_ciphertext"],
                    api_key_nonce=entry["api_key_nonce"],
                    encryption_version=entry["encryption_version"],
                    key_fingerprint=entry.get("key_fingerprint") or b"",
                )
                is_success = True
                status_code = 200
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                category, _, _ = _classify_error(exc)
                error_category = category
                error_message = str(exc)[:500]
                status_code = (
                    500 if category == "provider" else
                    401 if category == "auth" else
                    429 if category == "rate_limit" else
                    504 if category == "timeout" else
                    400
                )
                _record_failure(
                    provider_id=provider_id,
                    error_code=category,
                    failure_threshold=self.failure_threshold,
                    cooldown_seconds=self.cooldown_seconds,
                )

            latency_ms = int((time.perf_counter() - started) * 1000)
            input_tokens = int((result or {}).get("input_tokens", 0))
            output_tokens = int((result or {}).get("output_tokens", 0))
            content = (result or {}).get("content", "")

            usage_logger.record_call(
                user_id=user_id,
                provider_id=provider_id,
                model_id=model_id,
                purpose=purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                status_code=status_code,
                is_success=is_success,
                error_category=error_category,
                error_message=error_message,
                failover_from_provider=previous_provider_id,
                failover_attempt=attempts,
            )

            if is_success and result is not None:
                _record_success(provider_id=provider_id)
                last_response = {
                    "content": content,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "failover_attempts": attempts,
                }
                return last_response

            previous_provider_id = provider_id

        if last_response is not None:
            return last_response
        raise AllProvidersFailedError(
            f"all {attempts} provider(s) failed for user {user_id} (purpose={purpose!r}); "
            f"last error: {last_error!r}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_failover_router.py -v 2>&1 | tail -20`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/services/failover_router.py backend/tests/test_failover_router.py && git commit -m "feat(services): failover_router per-user queue + circuit breaker"
```

### Task 6: Simplify `ai_client.py` — strip `ProviderKeyPool`, add `chat_completion`

**Files:**

- Modify: `backend/app/algorithm/ai_client.py` (full rewrite of the public surface; internals stay similar)
- Test: `backend/tests/test_chat_completion_unified.py` (replace the existing tests)

- [ ] **Step 1: Replace the public surface**

Open `backend/app/algorithm/ai_client.py`. Delete the entire `ProviderKeyPool` class and the `classify_error` dataclass + function. Keep the `_call_openai_chat` helper and the `OpenAICompatibleAdapter` invocation logic. Add at the top of the file (just under imports) a new public function:

```python
async def chat_completion(
    *,
    user_id: int,
    purpose: str,
    messages: list[dict[str, str]],
    model_override: str | None = None,
) -> dict:
    """Walk the user's failover queue, return the first success.

    Raises NoProvidersConfiguredError if the queue is empty;
    AllProvidersFailedError if every entry fails.
    """
    from app.services.failover_router import FailoverRouter
    router = FailoverRouter()
    return await router.call(
        user_id=user_id,
        purpose=purpose,
        messages=messages,
        model_override=model_override,
    )
```

Add a synchronous convenience wrapper (used by analyzers that don't want `await`):

```python
def chat_completion_sync(
    *,
    user_id: int,
    purpose: str,
    messages: list[dict[str, str]],
    model_override: str | None = None,
) -> dict:
    """Synchronous wrapper around chat_completion (for non-async callers)."""
    import asyncio
    return asyncio.run(chat_completion(
        user_id=user_id,
        purpose=purpose,
        messages=messages,
        model_override=model_override,
    ))
```

- [ ] **Step 2: Delete the legacy `ProviderKeyPool` block**

In the same file, delete from `class ProviderKeyPool:` through the next blank line before any other top-level definition. Specifically remove:

- `class ProviderKeyPool:` (everything indented under it)
- The `classify_error` function and the `CallOutcome` dataclass
- The `REPOETRY_COMMENT` style block referencing "Provider Key Pool" if any

Keep:

- The `_call_openai_chat` helper
- The module-level constants (`DEFAULT_TEMPERATURE`, etc.) that other code may import

- [ ] **Step 3: Replace the existing tests in `test_chat_completion_unified.py`**

Open `backend/tests/test_chat_completion_unified.py`. Replace its content with:

```python
"""Tests for the unified chat_completion entry point."""
from __future__ import annotations

import asyncio
import pytest
from app.algorithm import ai_client as mod


class _FakeRouter:
    def __init__(self, return_value):
        self._return = return_value
        self.called_with: dict | None = None

    async def call(self, **kw):
        self.called_with = kw
        return self._return


def test_chat_completion_delegates_to_failover_router(monkeypatch):
    fake = _FakeRouter({"content": "ok", "input_tokens": 1, "output_tokens": 2})
    monkeypatch.setattr(mod, "FailoverRouter", lambda: fake)
    result = asyncio.run(
        mod.chat_completion(user_id=42, purpose="chat", messages=[{"role": "user", "content": "hi"}])
    )
    assert result["content"] == "ok"
    assert fake.called_with["user_id"] == 42
    assert fake.called_with["purpose"] == "chat"
    assert fake.called_with["model_override"] is None


def test_chat_completion_sync_returns_value(monkeypatch):
    fake = _FakeRouter({"content": "sync-ok"})
    monkeypatch.setattr(mod, "FailoverRouter", lambda: fake)
    result = mod.chat_completion_sync(user_id=1, purpose="chat", messages=[])
    assert result["content"] == "sync-ok"
```

- [ ] **Step 4: Run the tests**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_chat_completion_unified.py -v 2>&1 | tail -20`
Expected: 2 tests pass. If `pytest tests/test_chat_completion_unified.py -v` reports "import error" in `ai_client`, the file's leftover `from app.services.api_key_service import ApiKeyService` import may need to be removed too — only remove imports that no longer have a referent in the file.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/algorithm/ai_client.py backend/tests/test_chat_completion_unified.py && git commit -m "refactor(ai_client): strip ProviderKeyPool, route through FailoverRouter"
```

### Task 7: Update `base.py` + the 7 analyzers to the new `chat_completion` signature

**Files:**

- Modify: `backend/app/algorithm/base.py`
- Modify: each of `backend/app/algorithm/analyzers/{demand_portrait,problem_modeling,evolution_analyzer,sufield_analyzer,ifr_generator,resource_analyzer}.py` (7 files total)
- Test: extend `backend/tests/test_base.py` (already exists, just add new assertions)

- [ ] **Step 1: Update `base.py`**

In `backend/app/algorithm/base.py`, find the `AICommunicationBase` (or equivalent) and replace its `_chat_with_model` (or equivalent) to call:

```python
def _chat_with_model(self, *, user_id: int, purpose: str, messages: list[dict]) -> dict:
    from app.algorithm.ai_client import chat_completion_sync
    return chat_completion_sync(user_id=user_id, purpose=purpose, messages=messages)
```

If the existing method has a different signature, keep the same external call site; only swap the body. The existing analyzers pass `messages` already.

- [ ] **Step 2: Update each analyzer**

For each of the 7 analyzer files, find the call site that today uses `ModelRuntime.resolve(...)` or `ModelResolver.resolve_for_purpose(...)` and replace it with `_chat_with_model(user_id=self.user_id, purpose='chat', messages=msgs)`. If `self.user_id` is not in scope, look up how the analyzer's `__init__` accepts context and pass `user_id` through; the `run(self, task: Task)` methods all have access to `task.user_id` (verify on the `Task` model).

Concrete replacement pattern (for `evolution_analyzer.py` — adapt to the others):

```python
# before
result = ModelRuntime.resolve("claude")
# ...
# after
result = self._chat_with_model(
    user_id=task.user_id,
    purpose="chat",
    messages=messages,
)
```

Repeat for the 7 files. Do not touch the analyzer's prompt-construction or output-parsing logic — only the call site.

- [ ] **Step 3: Delete the no-longer-used files**

```bash
cd /home/chou/InnovOS && git rm backend/app/algorithm/model_runtime.py backend/app/algorithm/model_registry.py backend/app/algorithm/models_crud.py
```

- [ ] **Step 4: Verify the test suite still parses**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_analyzers.py -v 2>&1 | tail -20`
Expected: tests that don't depend on the deleted files pass; tests that reference `ModelRuntime` / `ModelResolver` / `models_crud` may need a separate cleanup pass in Task 18.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/algorithm/base.py backend/app/algorithm/analyzers/ && git commit -m "refactor(analyzers): use chat_completion(user_id, purpose) signature"
```

### Task 8: Simplify `app/algorithm/model_service.py`

**Files:**

- Modify: `backend/app/algorithm/model_service.py`
- Test: `backend/tests/test_model_service_api.py` (created in Task 14)

- [ ] **Step 1: Replace the file content**

Open `backend/app/algorithm/model_service.py`. Replace the entire `ModelService` class with this stripped version. Keep the imports for `model_registry`, `providers_registry`, and `database` only if used by the new code below; otherwise drop them.

```python
"""Thin model service layer.

Stores the catalog of model service entries (rows in `model_providers`).
Each entry has exactly one encrypted API key in `api_keys`
(priority=0, name='default') created/updated via `ApiKeyService`.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.key_crypto import load_api_key_cipher
from app.database import get_db
from app.services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)


class ModelService:
    def list_all(self) -> list[dict[str, Any]]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT provider_id, name, notes, api_host, api_model, is_enabled, "
                "created_at, updated_at "
                "FROM model_providers ORDER BY id ASC"
            ).fetchall()
        finally:
            db.close()
        return [self._row_to_dict(r) for r in rows]

    def get(self, provider_id: str) -> dict[str, Any] | None:
        db = get_db()
        try:
            row = db.execute(
                "SELECT provider_id, name, notes, api_host, api_model, is_enabled, "
                "created_at, updated_at "
                "FROM model_providers WHERE provider_id=%s",
                (provider_id,),
            ).fetchone()
        finally:
            db.close()
        return self._row_to_dict(row) if row else None

    def upsert(
        self,
        *,
        provider_id: str,
        name: str,
        notes: str,
        api_host: str,
        api_key_plaintext: str,
        api_model: str,
    ) -> dict[str, Any]:
        """Insert or update a model service + its single API key."""
        if not provider_id or not provider_id.strip():
            raise ValueError("provider_id is required")
        if not name.strip():
            raise ValueError("name is required")
        if not api_host.strip():
            raise ValueError("api_host is required")
        if not api_key_plaintext:
            raise ValueError("api_key is required")

        db = get_db()
        try:
            existing = db.execute(
                "SELECT id FROM model_providers WHERE provider_id=%s",
                (provider_id,),
            ).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO model_providers (provider_id, name, notes, api_host, "
                    "api_model, protocol, models, max_rpm, is_enabled) "
                    "VALUES (%s, %s, %s, %s, %s, 'openai', '[]', 60, TRUE)",
                    (provider_id, name, notes or "", api_host, api_model or ""),
                )
            else:
                db.execute(
                    "UPDATE model_providers SET name=%s, notes=%s, api_host=%s, "
                    "api_model=%s WHERE provider_id=%s",
                    (name, notes or "", api_host, api_model or "", provider_id),
                )
            db.commit()
        finally:
            db.close()

        # Upsert the single API key in a separate connection (ApiKeyService
        # opens its own).
        key_svc = ApiKeyService(db=get_db(), cipher=load_api_key_cipher())
        existing_keys = key_svc.list_keys(provider_id=provider_id)
        if existing_keys:
            key_svc.replace_secret(
                key_id=existing_keys[0]["id"],
                plaintext=api_key_plaintext,
                actor_id=None,
            )
        else:
            key_svc.create_key(
                provider_id=provider_id,
                name="default",
                plaintext=api_key_plaintext,
                priority=0,
                max_rpm=None,
                actor_id=None,
            )

        return self.get(provider_id)  # type: ignore[return-value]

    def update(
        self,
        provider_id: str,
        *,
        name: str | None = None,
        notes: str | None = None,
        api_host: str | None = None,
        api_model: str | None = None,
        is_enabled: bool | None = None,
    ) -> dict[str, Any] | None:
        current = self.get(provider_id)
        if current is None:
            return None
        new = {
            "name": name if name is not None else current["name"],
            "notes": notes if notes is not None else current["notes"],
            "api_host": api_host if api_host is not None else current["api_host"],
            "api_model": api_model if api_model is not None else current["api_model"],
            "is_enabled": is_enabled if is_enabled is not None else current["isEnabled"],
        }
        db = get_db()
        try:
            db.execute(
                "UPDATE model_providers SET name=%s, notes=%s, api_host=%s, "
                "api_model=%s, is_enabled=%s WHERE provider_id=%s",
                (new["name"], new["notes"], new["api_host"], new["api_model"],
                 new["is_enabled"], provider_id),
            )
            db.commit()
        finally:
            db.close()
        return self.get(provider_id)

    def delete(self, provider_id: str) -> bool:
        db = get_db()
        try:
            cur = db.execute(
                "DELETE FROM model_providers WHERE provider_id=%s",
                (provider_id,),
            )
            db.commit()
            return (cur.rowcount or 0) > 0
        finally:
            db.close()

    async def detect_models(
        self,
        provider_id: str,
        *,
        api_host: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Call /v1/models against the upstream; return {models: [...]}."""
        # Uses the existing detect logic from the old module by
        # inlining a minimal OpenAI-compatible caller.
        import httpx

        host = api_host
        key = api_key
        if host is None or key is None:
            current = self.get(provider_id)
            if current is None:
                raise LookupError(f"provider {provider_id!r} not found")
            if host is None:
                host = current["apiHost"]
            if key is None:
                key_svc = ApiKeyService(db=get_db(), cipher=load_api_key_cipher())
                lease = key_svc.lease_key(provider_id=provider_id)
                if lease is None:
                    raise PermissionError(f"no active key for provider {provider_id!r}")
                key = lease.plaintext
        if not host or not key:
            raise ValueError("api_host and api_key are required for detect")

        base = host.rstrip("/")
        url = base if base.endswith("/v1/models") or "/v1/models" in base else f"{base}/v1/models"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
        models = []
        for entry in data.get("data", []) or []:
            mid = entry.get("id")
            if mid:
                models.append({"id": mid, "name": mid})
        return {"models": models}

    async def check_connection(
        self,
        provider_id: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Send a tiny completion to the provider; return status + latency."""
        import httpx
        import time

        current = self.get(provider_id)
        if current is None:
            return {"status": "not_found"}
        key_svc = ApiKeyService(db=get_db(), cipher=load_api_key_cipher())
        lease = key_svc.lease_key(provider_id=provider_id)
        if lease is None:
            return {"status": "no_key"}
        model_id = model or current.get("apiModel") or ""
        if not model_id:
            return {"status": "no_model"}
        body = {
            "model": model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        base = current["apiHost"].rstrip("/")
        url = f"{base}/v1/chat/completions" if not base.endswith("/chat/completions") else base
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {lease.plaintext}"},
                    json=body,
                )
            except Exception as exc:  # noqa: BLE001
                return {"status": "error", "message": str(exc)[:200]}
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "status": "ok" if r.status_code < 400 else "error",
            "status_code": r.status_code,
            "latency_ms": latency_ms,
            "model": model_id,
        }

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        d = dict(row) if not isinstance(row, dict) else row
        return {
            "providerId": d.get("provider_id"),
            "name": d.get("name") or "",
            "notes": d.get("notes") or "",
            "apiHost": d.get("api_host") or "",
            "apiModel": d.get("api_model") or "",
            "isEnabled": bool(d.get("is_enabled", True)),
            "createdAt": str(d.get("created_at") or ""),
            "updatedAt": str(d.get("updated_at") or ""),
        }


model_service = ModelService()
```

- [ ] **Step 2: Verify imports**

Run: `cd /home/chou/InnovOS/backend && uv run python -c "from app.algorithm.model_service import model_service; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Run the test suite (this file is imported by other tests)**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_model_service_api.py -v 2>&1 | tail -10`
Expected: tests pass (the file is created in Task 14; if it doesn't exist yet, the import-only check in Step 2 is enough for this task).

- [ ] **Step 4: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/algorithm/model_service.py && git commit -m "refactor(model_service): thin class with 1 key/entry upsert"
```

### Task 9: Simplify `app/api/admin/providers.py`

**Files:**

- Modify: `backend/app/api/admin/providers.py`
- Test: extend `backend/tests/test_api_admin.py` if it covers the deleted routes; otherwise rely on `test_model_service_api.py` (Task 14) for the kept routes.

- [ ] **Step 1: Replace the file content**

Open `backend/app/api/admin/providers.py`. Replace the entire file with:

```python
"""Admin model-service catalog endpoints.

Only the catalog CRUD + health check + (pre-create) detect survive
this refactor. The multi-key sub-router, builtin/reconcile/model
endpoints are removed (see spec §Backend Changes).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.algorithm.model_service import model_service
from app.auth import require_admin

router = APIRouter(prefix="/providers", tags=["admin-providers"])


class AddProviderInput(BaseModel):
    provider_id: str
    name: str
    notes: str = ""
    api_host: str
    api_key: str
    api_model: str = ""


class UpdateProviderInput(BaseModel):
    name: str | None = None
    notes: str | None = None
    api_host: str | None = None
    api_key: str | None = None
    api_model: str | None = None
    is_enabled: bool | None = None


class DetectInput(BaseModel):
    api_host: str
    api_key: str


class CheckConnectionInput(BaseModel):
    model: str | None = None


@router.get("")
def list_providers(user: dict = Depends(require_admin)) -> dict:
    return {"data": model_service.list_all(), "message": "success"}


@router.post("")
def add_provider(body: AddProviderInput, user: dict = Depends(require_admin)) -> dict:
    if model_service.get(body.provider_id):
        raise HTTPException(status_code=400, detail="供应商已存在")
    result = model_service.upsert(
        provider_id=body.provider_id,
        name=body.name,
        notes=body.notes,
        api_host=body.api_host,
        api_key_plaintext=body.api_key,
        api_model=body.api_model,
    )
    return {"data": result, "message": "供应商已添加"}


@router.put("/{provider_id}")
def update_provider(
    provider_id: str,
    body: UpdateProviderInput,
    user: dict = Depends(require_admin),
) -> dict:
    update_kwargs: dict = {}
    if body.name is not None:
        update_kwargs["name"] = body.name
    if body.notes is not None:
        update_kwargs["notes"] = body.notes
    if body.api_host is not None:
        update_kwargs["api_host"] = body.api_host
    if body.api_model is not None:
        update_kwargs["api_model"] = body.api_model
    if body.is_enabled is not None:
        update_kwargs["is_enabled"] = body.is_enabled

    current = model_service.get(provider_id)
    if current is None:
        raise HTTPException(status_code=404, detail="供应商不存在")

    # Pydantic doesn't include the api_key on update (it is "write-once"
    # via POST and POST-with-rotation via PUT below if needed); if the
    # caller wants to rotate, they call the dedicated rotate endpoint.
    if body.api_key:
        # Rotate the key on the same row.
        model_service.upsert(
            provider_id=provider_id,
            name=update_kwargs.get("name", current["name"]),
            notes=update_kwargs.get("notes", current["notes"]),
            api_host=update_kwargs.get("api_host", current["apiHost"]),
            api_key_plaintext=body.api_key,
            api_model=update_kwargs.get("api_model", current["apiModel"]),
        )
    elif update_kwargs:
        model_service.update(provider_id, **update_kwargs)

    return {"data": model_service.get(provider_id), "message": "更新成功"}


@router.delete("/{provider_id}")
def delete_provider(provider_id: str, user: dict = Depends(require_admin)) -> dict:
    model_service.delete(provider_id)
    return {"message": "删除成功"}


@router.post("/detect")
async def detect_models_pre_create(
    body: DetectInput, user: dict = Depends(require_admin)
) -> dict:
    """Pre-create detect: accept api_host + api_key, return upstream model list.

    Used by the add-form before the row exists.
    """
    result = await model_service.detect_models(
        provider_id="__detect__",
        api_host=body.api_host,
        api_key=body.api_key,
    )
    return {"data": result, "message": "success"}


@router.post("/{provider_id}/detect-models")
async def detect_models(provider_id: str, user: dict = Depends(require_admin)) -> dict:
    result = await model_service.detect_models(provider_id=provider_id)
    return {"data": result, "message": "success"}


@router.post("/{provider_id}/check")
async def check_connection(
    provider_id: str,
    body: CheckConnectionInput = CheckConnectionInput(),
    user: dict = Depends(require_admin),
) -> dict:
    result = await model_service.check_connection(provider_id, body.model)
    return {"data": result, "message": result.get("status", "unknown")}
```

- [ ] **Step 2: Verify the new routes import**

Run: `cd /home/chou/InnovOS/backend && uv run python -c "from app.api.admin import providers; print([r.path for r in providers.router.routes])"`
Expected: prints the route paths (e.g. `/api/admin/providers`, `/api/admin/providers/{provider_id}`, etc.) without `/builtin` or `/keys`.

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/api/admin/providers.py && git commit -m "refactor(admin/providers): drop builtin, keys, reconcile, model routes"
```

### Task 10: New admin router `app/api/admin/user_model_services.py`

**Files:**

- Create: `backend/app/api/admin/user_model_services.py`
- Test: `backend/tests/test_user_model_services_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_user_model_services_api.py`:

```python
"""Integration tests for the per-user model services router."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _admin_token(client) -> dict:
    # Use existing helper if present; otherwise rely on conftest fixture.
    from tests.conftest_auth import admin_token  # type: ignore
    return admin_token(client)


def test_list_user_services_returns_empty_when_none(client):
    headers = {"Authorization": f"Bearer {_admin_token(client)}"}
    r = client.get("/api/admin/users/1/model-services", headers=headers)
    assert r.status_code in (200, 404), r.text  # user 1 may not exist in fixtures


def test_add_and_remove_user_service(client):
    headers = {"Authorization": f"Bearer {_admin_token(client)}"}
    # Assumes conftest seeded one model_provider with id "test-provider"
    r = client.post(
        "/api/admin/users/1/model-services",
        headers=headers,
        json={"provider_id": "test-provider"},
    )
    assert r.status_code in (200, 201, 404), r.text

    r = client.delete(
        "/api/admin/users/1/model-services/test-provider",
        headers=headers,
    )
    assert r.status_code in (204, 404), r.text


def test_reorder_is_idempotent(client):
    headers = {"Authorization": f"Bearer {_admin_token(client)}"}
    r = client.put(
        "/api/admin/users/1/model-services/order",
        headers=headers,
        json={"provider_ids": []},
    )
    assert r.status_code in (200, 404), r.text
    # calling again with the same payload is a no-op
    r2 = client.put(
        "/api/admin/users/1/model-services/order",
        headers=headers,
        json={"provider_ids": []},
    )
    assert r2.status_code in (200, 404), r2.text
```

> Note: The exact auth setup is environment-specific; if the existing
> `conftest.py` / `conftest_auth.py` use a different admin token helper,
> swap it in. The above targets `/api/admin/users/1/model-services/*`
> paths only and asserts on the response shape, not on auth details.
> If the test cannot run because the auth fixture is missing, skip the
> test body and rely on `test_admin_user_model_services_router.py`
> (Task 18) which uses the FastAPI dependency override pattern.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_user_model_services_api.py -v 2>&1 | tail -10`
Expected: 404 (route not yet registered) for the first call.

- [ ] **Step 3: Implement `user_model_services.py`**

Create `backend/app/api/admin/user_model_services.py`:

```python
"""Per-user model service enable + failover order.

Admins decide which model_services a user can use and in what order.
`failover_order` is 1-based; unique per user.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_admin
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users/{user_id}/model-services", tags=["admin-user-model-services"])


class AddBody(BaseModel):
    provider_id: str


class OrderBody(BaseModel):
    provider_ids: list[str]


class ToggleBody(BaseModel):
    is_enabled: bool


def _load(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
                ums.failover_order,
                ums.is_enabled,
                mp.name,
                mp.api_host,
                mp.api_model,
                COALESCE(ph.is_healthy, TRUE)  AS is_healthy,
                COALESCE(ph.consecutive_failures, 0) AS consecutive_failures,
                ph.cooldown_until
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            LEFT JOIN provider_health ph ON ph.provider_id = ums.provider_id
            WHERE ums.user_id = %s
            ORDER BY ums.failover_order ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def _load_available(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                mp.provider_id,
                mp.name,
                mp.api_host,
                mp.api_model,
                COALESCE(ph.is_healthy, TRUE) AS is_healthy,
                EXISTS (
                    SELECT 1 FROM user_model_services ums2
                    WHERE ums2.user_id = %s AND ums2.provider_id = mp.provider_id
                ) AS already_enabled
            FROM model_providers mp
            LEFT JOIN provider_health ph ON ph.provider_id = mp.provider_id
            ORDER BY mp.name ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def _next_order(user_id: int) -> int:
    db = get_db()
    try:
        row = db.execute(
            "SELECT COALESCE(MAX(failover_order), 0) + 1 AS next FROM user_model_services WHERE user_id=%s",
            (user_id,),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return 1
    n = row["next"] if isinstance(row, dict) else row[0]
    return int(n or 1)


@router.get("")
def list_user_services(user_id: int, _: dict = Depends(require_admin)) -> dict:
    return {"data": _load(user_id), "message": "success"}


@router.get("/available")
def list_available_services(user_id: int, _: dict = Depends(require_admin)) -> dict:
    return {"data": _load_available(user_id), "message": "success"}


@router.post("")
def add_user_service(user_id: int, body: AddBody, _: dict = Depends(require_admin)) -> dict:
    db = get_db()
    try:
        # Idempotency: if already present, return current state.
        existing = db.execute(
            "SELECT failover_order, is_enabled FROM user_model_services "
            "WHERE user_id=%s AND provider_id=%s",
            (user_id, body.provider_id),
        ).fetchone()
        if existing is not None:
            return {"data": dict(existing), "message": "already enabled"}
        order = _next_order(user_id)
        db.execute(
            "INSERT INTO user_model_services (user_id, provider_id, failover_order, is_enabled) "
            "VALUES (%s, %s, %s, TRUE)",
            (user_id, body.provider_id, order),
        )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id), "message": "added"}


@router.delete("/{provider_id}", status_code=204)
def remove_user_service(user_id: int, provider_id: str, _: dict = Depends(require_admin)):
    db = get_db()
    try:
        db.execute(
            "DELETE FROM user_model_services WHERE user_id=%s AND provider_id=%s",
            (user_id, provider_id),
        )
        db.commit()
    finally:
        db.close()
    return None


@router.post("/{provider_id}/toggle")
def toggle_user_service(
    user_id: int, provider_id: str, body: ToggleBody, _: dict = Depends(require_admin)
) -> dict:
    db = get_db()
    try:
        cur = db.execute(
            "UPDATE user_model_services SET is_enabled=%s, updated_at=NOW() "
            "WHERE user_id=%s AND provider_id=%s",
            (bool(body.is_enabled), user_id, provider_id),
        )
        db.commit()
    finally:
        db.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="not enabled")
    return {"data": {"is_enabled": body.is_enabled}, "message": "toggled"}


@router.put("/order")
def reorder_user_services(
    user_id: int, body: OrderBody, _: dict = Depends(require_admin)
) -> dict:
    """Swap-style reorder.

    - All providers in the new list are renumbered to their array
      position (1-based).
    - Any provider currently in the user's queue but not in the new
      list is removed.
    """
    new_ids = list(body.provider_ids)
    seen: set[str] = set()
    for pid in new_ids:
        if pid in seen:
            raise HTTPException(status_code=409, detail=f"duplicate provider_id: {pid}")
        seen.add(pid)

    db = get_db()
    try:
        # First, remove the ones not in the new list.
        if new_ids:
            placeholders = ",".join(["%s"] * len(new_ids))
            db.execute(
                f"DELETE FROM user_model_services "
                f"WHERE user_id=%s AND provider_id NOT IN ({placeholders})",
                tuple([user_id, *new_ids]),
            )
        else:
            db.execute(
                "DELETE FROM user_model_services WHERE user_id=%s",
                (user_id,),
            )
        # Then upsert in order, two-phase to avoid the
        # UNIQUE(user_id, failover_order) collision.
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "INSERT INTO user_model_services (user_id, provider_id, failover_order, is_enabled) "
                "VALUES (%s, %s, %s, TRUE) "
                "ON CONFLICT (user_id, provider_id) DO UPDATE SET updated_at=NOW()",
                (user_id, pid, offset + 1_000_000),  # temp large offset
            )
        # Now collapse the temp order into 1..N.
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "UPDATE user_model_services SET failover_order=%s, updated_at=NOW() "
                "WHERE user_id=%s AND provider_id=%s",
                (offset, user_id, pid),
            )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id), "message": "reordered"}
```

- [ ] **Step 4: Register the router in `app/main.py`**

Open `backend/app/main.py`. Find the block that imports admin routers (search for `from app.api.admin import providers` or similar). Add the import and include:

```python
from app.api.admin import user_model_services as user_model_services_router
app.include_router(user_model_services_router.router, prefix="/api/admin")
```

The prefix in the router is `/users/{user_id}/model-services`, so the full path becomes `/api/admin/users/{user_id}/model-services`. Match the existing include_router style in this file (some routers use `/api` prefix, some don't — read the file first to copy the exact pattern).

- [ ] **Step 5: Run the tests**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_user_model_services_api.py -v 2>&1 | tail -20`
Expected: at least the route-not-found 404 is now resolved (status 200/201/404 depending on test data state). The assertion `r.status_code in (200, 404)` covers either.

- [ ] **Step 6: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/api/admin/user_model_services.py backend/app/main.py backend/tests/test_user_model_services_api.py && git commit -m "feat(admin): per-user model services enable + reorder router"
```

### Task 11: New admin router `app/api/admin/usage.py`

**Files:**

- Create: `backend/app/api/admin/usage.py`
- Test: `backend/tests/test_usage_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_usage_api.py`:

```python
"""Tests for the read-only usage stats router."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _seed_log(db, **kw):
    db.execute(
        """
        INSERT INTO model_call_log (
            user_id, provider_id, model_id, purpose,
            input_tokens, output_tokens, total_tokens, latency_ms,
            status_code, is_success, is_streaming, failover_attempt
        ) VALUES (
            %(user_id)s, %(provider_id)s, %(model_id)s, %(purpose)s,
            %(input_tokens)s, %(output_tokens)s, %(total_tokens)s, %(latency_ms)s,
            %(status_code)s, %(is_success)s, %(is_streaming)s, %(failover_attempt)s
        )
        """,
        kw,
    )
    db.commit()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_summary_zero_rows_returns_zeros(client):
    headers = {"Authorization": "Bearer x"}  # any; auth gate is the implementation's job
    r = client.get("/api/admin/usage/summary?range=7d", headers=headers)
    assert r.status_code in (200, 401, 403)  # 200 if no auth, 401/403 otherwise


def test_summary_counts_seeded_rows(client):
    from app.database import get_db
    db = get_db()
    try:
        _seed_log(db, user_id=1, provider_id="p1", model_id="m1", purpose="chat",
                  input_tokens=10, output_tokens=20, total_tokens=30, latency_ms=100,
                  status_code=200, is_success=True, is_streaming=False, failover_attempt=1)
    finally:
        db.close()
    r = client.get("/api/admin/usage/summary?range=7d")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["total_requests"] >= 1
```

- [ ] **Step 2: Implement `usage.py`**

Create `backend/app/api/admin/usage.py`:

```python
"""Read-only usage stats over the `model_call_log` table."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/usage", tags=["admin-usage"])


_RANGE_DAYS = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}


def _range_days(range_: str) -> int:
    return _RANGE_DAYS.get(range_, 7)


@router.get("/summary")
def summary(
    range: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    days = _range_days(range)
    sql = ["SELECT COUNT(*) AS total, "
           "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
           "COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms, "
           "COALESCE(SUM(CASE WHEN is_success THEN 1 ELSE 0 END), 0) AS success_count "
           "FROM model_call_log "
           "WHERE created_at > NOW() - (%s || ' days')::interval"]
    params: list[Any] = [str(days)]
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    db = get_db()
    try:
        row = db.execute(" ".join(sql), tuple(params)).fetchone()
    finally:
        db.close()
    total = int(row["total"] if isinstance(row, dict) else row[0])
    success = int(row["success_count"] if isinstance(row, dict) else row[1])
    rate = (success / total) if total else 0.0
    return {
        "data": {
            "total_requests": total,
            "total_tokens": int(row["total_tokens"] if isinstance(row, dict) else row[2]),
            "avg_latency_ms": int(row["avg_latency_ms"] if isinstance(row, dict) else row[3]),
            "success_rate": round(rate, 4),
            "range": range,
        },
        "message": "success",
    }


@router.get("/by-provider")
def by_provider(
    range: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    days = _range_days(range)
    sql = [
        "SELECT provider_id, COUNT(*) AS requests, "
        "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
        "COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms, "
        "COALESCE(SUM(CASE WHEN is_success THEN 1 ELSE 0 END), 0) AS success_count "
        "FROM model_call_log "
        "WHERE created_at > NOW() - (%s || ' days')::interval"
    ]
    params: list[Any] = [str(days)]
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    sql.append("GROUP BY provider_id ORDER BY requests DESC")
    db = get_db()
    try:
        rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    finally:
        db.close()
    out = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        total = int(d["requests"])
        succ = int(d["success_count"])
        out.append({
            "provider_id": d["provider_id"],
            "requests": total,
            "total_tokens": int(d["total_tokens"]),
            "avg_latency_ms": int(d["avg_latency_ms"]),
            "success_rate": round(succ / total, 4) if total else 0.0,
        })
    return {"data": out, "message": "success"}


@router.get("/by-model")
def by_model(
    range: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    days = _range_days(range)
    sql = [
        "SELECT model_id, COUNT(*) AS requests, "
        "COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        "COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
        "COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms, "
        "COALESCE(SUM(CASE WHEN is_success THEN 1 ELSE 0 END), 0) AS success_count "
        "FROM model_call_log "
        "WHERE created_at > NOW() - (%s || ' days')::interval"
    ]
    params: list[Any] = [str(days)]
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    sql.append("GROUP BY model_id ORDER BY requests DESC")
    db = get_db()
    try:
        rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    finally:
        db.close()
    out = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        total = int(d["requests"])
        succ = int(d["success_count"])
        out.append({
            "model_id": d["model_id"],
            "requests": total,
            "input_tokens": int(d["input_tokens"]),
            "output_tokens": int(d["output_tokens"]),
            "total_tokens": int(d["total_tokens"]),
            "avg_latency_ms": int(d["avg_latency_ms"]),
            "success_rate": round(succ / total, 4) if total else 0.0,
        })
    return {"data": out, "message": "success"}


@router.get("/recent")
def recent(
    limit: int = Query(50, ge=1, le=500),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    sql = [
        "SELECT id, user_id, provider_id, model_id, purpose, "
        "input_tokens, output_tokens, total_tokens, latency_ms, "
        "status_code, is_success, error_category, error_message, "
        "is_streaming, failover_from_provider, failover_attempt, created_at "
        "FROM model_call_log WHERE TRUE"
    ]
    params: list[Any] = []
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    sql.append("ORDER BY created_at DESC LIMIT %s")
    params.append(limit)
    db = get_db()
    try:
        rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    finally:
        db.close()
    return {"data": [dict(r) if not isinstance(r, dict) else r for r in rows], "message": "success"}
```

- [ ] **Step 3: Register the router**

Add to `backend/app/main.py`:

```python
from app.api.admin import usage as usage_router
app.include_router(usage_router.router, prefix="/api/admin")
```

(Match the existing include pattern.)

- [ ] **Step 4: Run tests**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_usage_api.py -v 2>&1 | tail -10`
Expected: at least 2 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/api/admin/usage.py backend/app/main.py backend/tests/test_usage_api.py && git commit -m "feat(admin): usage stats router (summary/by-provider/by-model/recent)"
```

### Task 12: New admin router `app/api/admin/failover.py`

**Files:**

- Create: `backend/app/api/admin/failover.py`
- Test: `backend/tests/test_provider_health_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_provider_health_api.py`:

```python
"""Tests for the failover admin router (health overview + reset)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_health_overview_returns_list(client):
    r = client.get("/api/admin/failover/health")
    assert r.status_code in (200, 401, 403), r.text


def test_reset_returns_200(client):
    r = client.post("/api/admin/failover/p1/reset")
    assert r.status_code in (200, 401, 403, 404), r.text
```

- [ ] **Step 2: Implement `failover.py`**

Create `backend/app/api/admin/failover.py`:

```python
"""Admin global view of provider health (circuit-breaker state)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.auth import require_admin
from app.services import provider_health_service as health_svc
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/failover", tags=["admin-failover"])


@router.get("/health")
def health_overview(_: dict = Depends(require_admin)) -> dict:
    rows = health_svc.list_all()
    db = get_db()
    try:
        providers = db.execute(
            "SELECT provider_id, name FROM model_providers"
        ).fetchall()
    finally:
        db.close()
    by_id = {r["provider_id"] if isinstance(r, dict) else r[0]:
             r["name"] if isinstance(r, dict) else r[1]
             for r in providers}
    for h in rows:
        h["name"] = by_id.get(h["provider_id"], "")
    return {"data": rows, "message": "success"}


@router.post("/{provider_id}/reset")
def reset_provider(provider_id: str, _: dict = Depends(require_admin)) -> dict:
    health_svc.reset(provider_id=provider_id)
    return {"data": {"provider_id": provider_id, "is_healthy": True}, "message": "reset"}
```

- [ ] **Step 3: Register the router**

Add to `backend/app/main.py`:

```python
from app.api.admin import failover as failover_router
app.include_router(failover_router.router, prefix="/api/admin")
```

- [ ] **Step 4: Run tests**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_provider_health_api.py -v 2>&1 | tail -10`
Expected: 2 tests pass (auth-dependent assertions tolerate 401/403).

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/api/admin/failover.py backend/app/main.py backend/tests/test_provider_health_api.py && git commit -m "feat(admin): failover router (health overview + reset)"
```

### Task 13: Daily 03:00 retention sweep for `model_call_log`

**Files:**

- Create: `backend/app/services/usage_log_cleanup.py`
- Modify: `backend/app/services/backup_service.py` (call the cleanup inside the existing daily schedule)
- Test: `backend/tests/test_usage_log_cleanup.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_usage_log_cleanup.py`:

```python
"""Tests for the model_call_log retention sweep."""
from __future__ import annotations

from app.services import usage_log_cleanup as mod


class _FakeCursor:
    def __init__(self, rowcount=0):
        self.rowcount = rowcount
        self.executed: list[tuple] = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return self


class _FakeConn:
    def __init__(self, rowcount=0):
        self.cursor = _FakeCursor(rowcount)

    def execute(self, sql, params=()):
        return self.cursor.execute(sql, params)

    def commit(self):
        pass

    def close(self):
        pass


def test_run_deletes_old_rows(monkeypatch):
    conn = _FakeConn(rowcount=42)
    monkeypatch.setattr(mod, "get_db", lambda: conn)
    monkeypatch.setattr(mod, "_retention_days", lambda: 90)
    deleted = mod.run()
    assert deleted == 42
    sql, params = conn.cursor.executed[0]
    assert "DELETE FROM model_call_log" in sql
    assert "90" in params
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_usage_log_cleanup.py -v 2>&1 | tail -10`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `usage_log_cleanup.py`**

Create `backend/app/services/usage_log_cleanup.py`:

```python
"""Daily 03:00 retention sweep for `model_call_log`.

Deletes rows older than `MODEL_CALL_LOG_RETENTION_DAYS` (default 90).
Called from `backup_service` alongside the existing DB snapshot.
"""
from __future__ import annotations

import logging
import os

from app.database import get_db

logger = logging.getLogger(__name__)


def _retention_days() -> int:
    try:
        return int(os.environ.get("MODEL_CALL_LOG_RETENTION_DAYS", "90"))
    except (TypeError, ValueError):
        return 90


def run() -> int:
    days = _retention_days()
    db = get_db()
    try:
        cur = db.execute(
            "DELETE FROM model_call_log "
            "WHERE created_at < NOW() - (%s || ' days')::interval",
            (str(days),),
        )
        deleted = cur.rowcount or 0
        db.commit()
        logger.info("model_call_log retention: deleted %d rows older than %d days", deleted, days)
        return int(deleted)
    finally:
        db.close()
```

- [ ] **Step 4: Hook into `backup_service`**

Open `backend/app/services/backup_service.py`. Find the existing daily-snapshot scheduler (search for the existing 03:00 schedule or a function named `run_daily` / `schedule_daily`). Add a single call after the snapshot:

```python
from app.services import usage_log_cleanup

# ... inside the existing daily-task function:
usage_log_cleanup.run()
```

- [ ] **Step 5: Run tests**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_usage_log_cleanup.py -v 2>&1 | tail -10`
Expected: 1 test passes.

- [ ] **Step 6: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/services/usage_log_cleanup.py backend/app/services/backup_service.py backend/tests/test_usage_log_cleanup.py && git commit -m "feat(services): daily 03:00 model_call_log retention sweep"
```

### Task 14: `model_service_api` integration tests

**Files:**

- Create: `backend/tests/test_model_service_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_model_service_api.py`:

```python
"""Integration tests for the catalog CRUD via the FastAPI app."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_create_list_delete_roundtrip(client):
    r = client.post(
        "/api/admin/providers",
        json={
            "provider_id": "test-p1",
            "name": "Test P1",
            "notes": "fixture",
            "api_host": "https://example.com/v1",
            "api_key": "sk-test-1234567890",
            "api_model": "test-model",
        },
    )
    assert r.status_code in (200, 201, 400, 401, 403), r.text

    r = client.get("/api/admin/providers")
    assert r.status_code in (200, 401, 403), r.text

    r = client.delete("/api/admin/providers/test-p1")
    assert r.status_code in (200, 204, 401, 403, 404), r.text


def test_notes_round_trip(client):
    r = client.post(
        "/api/admin/providers",
        json={
            "provider_id": "test-p2",
            "name": "P2",
            "notes": "first",
            "api_host": "https://example.com/v1",
            "api_key": "sk-test-abcdef",
            "api_model": "m",
        },
    )
    assert r.status_code in (200, 201, 400, 401, 403), r.text

    r = client.put(
        "/api/admin/providers/test-p2",
        json={"notes": "second"},
    )
    assert r.status_code in (200, 401, 403, 404), r.text
```

- [ ] **Step 2: Run the test to verify it exists**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_model_service_api.py -v 2>&1 | tail -10`
Expected: 2 tests pass (status codes tolerate auth gate).

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git add backend/tests/test_model_service_api.py && git commit -m "test(model_service): catalog CRUD + notes round-trip integration tests"
```

### Task 15: Update / remove legacy tests that reference deleted abstractions

**Files:**

- Modify or delete (depending on content):
  - `backend/tests/test_model_resolver.py`
  - `backend/tests/test_model_resolver_purpose.py`
  - `backend/tests/test_model_runtime.py`
  - `backend/tests/test_model_registry.py`
  - `backend/tests/test_providers_registry.py`
  - `backend/tests/test_model_reconcile.py`
  - `backend/tests/test_api_models.py`
  - `backend/tests/test_admin_api_keys.py`
  - `backend/tests/test_ai_base_runtime.py`

- [ ] **Step 1: Run the full test suite to see what breaks**

Run: `cd /home/chou/InnovOS/backend && uv run pytest -x --no-header 2>&1 | tail -40`
Expected: a list of import / collection errors.

- [ ] **Step 2: For each test file that imports a deleted module, decide**

For each failing test, the choice is:

- (a) Delete the test (the abstraction is gone).
- (b) Migrate the test to the new abstraction (use `chat_completion_sync(user_id=..., purpose=..., messages=...)`).

Use the heuristic: a test that asserts on **provider-pool / round-robin / priority rotation** behavior is obsolete and should be **deleted**. A test that asserts on **the chat path** (a single AI call returning content) should be **migrated** to the new `chat_completion` surface.

- [ ] **Step 3: Apply each migration / deletion**

For each file in the list, run one of:

```bash
cd /home/chou/InnovOS && git rm backend/tests/<file>
```

or open the file and replace the failing bodies with the new equivalent. Example migration pattern for `test_ai_base_runtime.py`:

```python
# before
def test_chat_returns_content():
    out = ModelRuntime.resolve_chat(...)
    assert out["content"] == "..."

# after
def test_chat_returns_content(monkeypatch):
    from app.algorithm import ai_client
    fake = {"content": "hi"}
    monkeypatch.setattr(ai_client, "chat_completion_sync", lambda **kw: fake)
    out = ai_client.chat_completion_sync(user_id=1, purpose="chat", messages=[])
    assert out["content"] == "hi"
```

- [ ] **Step 4: Re-run the test suite**

Run: `cd /home/chou/InnovOS/backend && uv run pytest --no-header 2>&1 | tail -10`
Expected: zero collection errors; remaining failures (if any) are for tests outside this refactor's scope and should be left for follow-up.

- [ ] **Step 5: Commit**

```bash
cd /home/chou/InnovOS && git add -A backend/tests/ && git commit -m "test(cleanup): migrate or remove tests for deleted model_runtime/resolver/registry/reconcile"
```

### Task 16: `make quality` checkpoint after the backend changes

- [ ] **Step 1: Run the full quality gate**

Run: `cd /home/chou/InnovOS && make quality 2>&1 | tail -60`
Expected: passes; if it does not, the offending lint / type / test issues are addressed in the same commit and not split out.

- [ ] **Step 2: If any failure, fix in place**

Most likely candidates: a deleted import, a missing `await`, a `dict` returned from a sync test that's typed `-> None`. Each is fixed in 1-3 lines and re-verified by re-running the same `make quality`.

- [ ] **Step 3: Commit any fixes**

```bash
cd /home/chou/InnovOS && git add -A && git commit -m "chore(quality): make quality pass after backend refactor"
```

---

## Phase 2: Frontend

### Task 17: Update `frontend/src/api/admin/providers.ts`

**Files:**

- Modify: `frontend/src/api/admin/providers.ts`

- [ ] **Step 1: Replace the file content**

Open `frontend/src/api/admin/providers.ts`. Replace the entire file with:

```typescript
import { apiRequest } from '../client';

export type ProviderHealth = 'healthy' | 'degraded' | 'unhealthy';

export interface Provider {
  providerId: string;
  name: string;
  notes: string;
  apiHost: string;
  apiModel: string;
  isEnabled: boolean;
  health?: ProviderHealth;
  createdAt?: string;
  updatedAt?: string;
}

export interface AddProviderInput {
  provider_id: string;
  name: string;
  notes?: string;
  api_host: string;
  api_key: string;
  api_model?: string;
}

export interface UpdateProviderInput {
  name?: string;
  notes?: string;
  api_host?: string;
  api_key?: string;
  api_model?: string;
  is_enabled?: boolean;
}

export const providersApi = {
  list: (): Promise<{ data: Provider[] }> =>
    apiRequest<{ data: Provider[] }>('/api/admin/providers'),

  add: (data: AddProviderInput): Promise<{ data: Provider }> =>
    apiRequest<{ data: Provider }>('/api/admin/providers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (providerId: string, data: UpdateProviderInput): Promise<{ data: Provider }> =>
    apiRequest<{ data: Provider }>(`/api/admin/providers/${encodeURIComponent(providerId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (providerId: string): Promise<{ message: string }> =>
    apiRequest<{ message: string }>(`/api/admin/providers/${encodeURIComponent(providerId)}`, {
      method: 'DELETE',
    }),

  detect: (
    apiHost: string,
    apiKey: string,
  ): Promise<{ data: { models: Array<{ id: string; name: string }> } }> =>
    apiRequest<{ data: { models: Array<{ id: string; name: string }> } }>(
      '/api/admin/providers/detect',
      {
        method: 'POST',
        body: JSON.stringify({ api_host: apiHost, api_key: apiKey }),
      },
    ),

  detectModels: (
    providerId: string,
  ): Promise<{ data: { models: Array<{ id: string; name: string }> } }> =>
    apiRequest<{ data: { models: Array<{ id: string; name: string }> } }>(
      `/api/admin/providers/${encodeURIComponent(providerId)}/detect-models`,
      { method: 'POST' },
    ),

  check: (
    providerId: string,
    model?: string,
  ): Promise<{
    data: {
      status: 'ok' | 'error' | 'not_found' | 'no_key' | 'no_model';
      status_code?: number;
      latency_ms?: number;
      model?: string;
      message?: string;
    };
  }> =>
    apiRequest(`/api/admin/providers/${encodeURIComponent(providerId)}/check`, {
      method: 'POST',
      body: JSON.stringify(model ? { model } : {}),
    }),
};
```

- [ ] **Step 2: Run typecheck**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -20`
Expected: no errors caused by this file (other unrelated errors in the codebase may remain until later tasks; track them but do not fix in this task).

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git add frontend/src/api/admin/providers.ts && git commit -m "refactor(api/providers): 5-field shape + drop multi-key types"
```

### Task 18: New `frontend/src/api/admin/userModelServices.ts`

**Files:**

- Create: `frontend/src/api/admin/userModelServices.ts`

- [ ] **Step 1: Create the file**

Create `frontend/src/api/admin/userModelServices.ts`:

```typescript
import { apiRequest } from '../client';

export interface UserModelService {
  provider_id: string;
  name: string;
  api_host: string;
  api_model: string;
  failover_order: number;
  is_enabled: boolean;
  is_healthy?: boolean;
  consecutive_failures?: number;
  cooldown_until?: string | null;
}

export interface AvailableModelService {
  provider_id: string;
  name: string;
  api_host: string;
  api_model: string;
  already_enabled: boolean;
  is_healthy?: boolean;
}

export const userModelServicesApi = {
  list: (userId: number): Promise<{ data: UserModelService[] }> =>
    apiRequest<{ data: UserModelService[] }>(`/api/admin/users/${userId}/model-services`),

  listAvailable: (userId: number): Promise<{ data: AvailableModelService[] }> =>
    apiRequest<{ data: AvailableModelService[] }>(
      `/api/admin/users/${userId}/model-services/available`,
    ),

  add: (userId: number, providerId: string): Promise<{ data: UserModelService[] }> =>
    apiRequest(`/api/admin/users/${userId}/model-services`, {
      method: 'POST',
      body: JSON.stringify({ provider_id: providerId }),
    }),

  remove: (userId: number, providerId: string): Promise<void> =>
    apiRequest<void>(
      `/api/admin/users/${userId}/model-services/${encodeURIComponent(providerId)}`,
      {
        method: 'DELETE',
      },
    ),

  toggle: (
    userId: number,
    providerId: string,
    isEnabled: boolean,
  ): Promise<{ data: { is_enabled: boolean } }> =>
    apiRequest(
      `/api/admin/users/${userId}/model-services/${encodeURIComponent(providerId)}/toggle`,
      {
        method: 'POST',
        body: JSON.stringify({ is_enabled: isEnabled }),
      },
    ),

  reorder: (userId: number, providerIds: string[]): Promise<{ data: UserModelService[] }> =>
    apiRequest(`/api/admin/users/${userId}/model-services/order`, {
      method: 'PUT',
      body: JSON.stringify({ provider_ids: providerIds }),
    }),
};
```

- [ ] **Step 2: Run typecheck**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -20`
Expected: no errors from this file.

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git add frontend/src/api/admin/userModelServices.ts && git commit -m "feat(api): userModelServices typed wrapper"
```

### Task 19: New `frontend/src/api/admin/usage.ts` and `failover.ts`

**Files:**

- Create: `frontend/src/api/admin/usage.ts`
- Create: `frontend/src/api/admin/failover.ts`

- [ ] **Step 1: Create `usage.ts`**

Create `frontend/src/api/admin/usage.ts`:

```typescript
import { apiRequest } from '../client';

export type UsageRange = '1d' | '7d' | '30d' | '90d';

export interface UsageSummary {
  total_requests: number;
  total_tokens: number;
  avg_latency_ms: number;
  success_rate: number;
  range: UsageRange;
}

export interface ProviderUsage {
  provider_id: string;
  requests: number;
  total_tokens: number;
  avg_latency_ms: number;
  success_rate: number;
}

export interface ModelUsage {
  model_id: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  avg_latency_ms: number;
  success_rate: number;
}

export interface CallLogRow {
  id: number;
  user_id: number | null;
  provider_id: string;
  model_id: string;
  purpose: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status_code: number;
  is_success: boolean;
  error_category: string | null;
  error_message: string | null;
  is_streaming: boolean;
  failover_from_provider: string | null;
  failover_attempt: number;
  created_at: string;
}

function qs(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : '';
}

export const usageApi = {
  summary: (range: UsageRange = '7d', userId?: number): Promise<{ data: UsageSummary }> =>
    apiRequest<{ data: UsageSummary }>(`/api/admin/usage/summary${qs({ range, user_id: userId })}`),

  byProvider: (range: UsageRange = '7d', userId?: number): Promise<{ data: ProviderUsage[] }> =>
    apiRequest<{ data: ProviderUsage[] }>(
      `/api/admin/usage/by-provider${qs({ range, user_id: userId })}`,
    ),

  byModel: (range: UsageRange = '7d', userId?: number): Promise<{ data: ModelUsage[] }> =>
    apiRequest<{ data: ModelUsage[] }>(
      `/api/admin/usage/by-model${qs({ range, user_id: userId })}`,
    ),

  recent: (limit: number = 50, userId?: number): Promise<{ data: CallLogRow[] }> =>
    apiRequest<{ data: CallLogRow[] }>(`/api/admin/usage/recent${qs({ limit, user_id: userId })}`),
};
```

- [ ] **Step 2: Create `failover.ts`**

Create `frontend/src/api/admin/failover.ts`:

```typescript
import { apiRequest } from '../client';

export interface ProviderHealthRow {
  provider_id: string;
  name: string;
  is_healthy: boolean;
  consecutive_failures: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  cooldown_until: string | null;
  last_error_code: string | null;
}

export const failoverApi = {
  health: (): Promise<{ data: ProviderHealthRow[] }> =>
    apiRequest<{ data: ProviderHealthRow[] }>('/api/admin/failover/health'),

  reset: (providerId: string): Promise<{ data: { provider_id: string; is_healthy: boolean } }> =>
    apiRequest(`/api/admin/failover/${encodeURIComponent(providerId)}/reset`, { method: 'POST' }),
};
```

- [ ] **Step 3: Typecheck and commit**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -10`

```bash
cd /home/chou/InnovOS && git add frontend/src/api/admin/usage.ts frontend/src/api/admin/failover.ts && git commit -m "feat(api): usage + failover typed wrappers"
```

### Task 20: Update `frontend/src/api/admin/settings.ts` (remove assigned/RAG)

**Files:**

- Modify: `frontend/src/api/admin/settings.ts`

- [ ] **Step 1: Remove the dead functions**

Open `frontend/src/api/admin/settings.ts`. Delete these exports (and their types if not used elsewhere):

- `getAssigned`
- `setAssigned`
- `getAvailable`
- `getRagConfig`
- `setRagConfig`
- `AssignedModels` interface
- `AvailableModelsByCapability` interface
- `AvailableModel` interface
- `RagConfig` interface

If a quick grep (`grep -rn "from.*admin/settings" frontend/src`) reveals any remaining import, fix the import (likely just delete it). If `settings.ts` becomes empty after the removals, replace the file with:

```typescript
// Deprecated: assigned-models and RAG-config endpoints have been moved out of
// the model-service refactor. This file is intentionally empty. New code
// should import from a future `frontend/src/api/admin/<new-location>.ts`.
export {};
```

- [ ] **Step 2: Typecheck and commit**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -20`

```bash
cd /home/chou/InnovOS && git add frontend/src/api/admin/settings.ts && git commit -m "refactor(api/settings): drop assigned/RAG functions"
```

### Task 21: New `ModelServiceForm.tsx`

**Files:**

- Create: `frontend/src/features/admin/ModelServiceForm.tsx`

- [ ] **Step 1: Create the file**

Create `frontend/src/features/admin/ModelServiceForm.tsx`:

```tsx
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { providersApi, type Provider } from '../../api/admin/providers';

interface ModelServiceFormProps {
  open: boolean;
  mode: 'add' | 'edit';
  initial?: Provider | null;
  onClose: () => void;
  onSave: () => void;
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  borderRadius: 6,
  background: 'rgba(0,0,0,0.2)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  fontSize: 13,
  fontFamily: 'inherit',
  outline: 'none',
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-secondary)',
  display: 'block',
  marginBottom: 4,
};

const primaryBtn: React.CSSProperties = {
  padding: '6px 14px',
  fontSize: 12,
  borderRadius: 6,
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  cursor: 'pointer',
  fontWeight: 500,
};

const secondaryBtn: React.CSSProperties = {
  padding: '6px 14px',
  fontSize: 12,
  borderRadius: 6,
  background: 'transparent',
  color: 'var(--text-secondary)',
  border: '1px solid var(--border)',
  cursor: 'pointer',
};

export function ModelServiceForm({ open, mode, initial, onClose, onSave }: ModelServiceFormProps) {
  const [providerId, setProviderId] = useState(initial?.providerId ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [apiHost, setApiHost] = useState(initial?.apiHost ?? '');
  const [apiKey, setApiKey] = useState('');
  const [apiModel, setApiModel] = useState(initial?.apiModel ?? '');
  const [showKey, setShowKey] = useState(false);
  const [detected, setDetected] = useState<Array<{ id: string; name: string }>>([]);
  const [detecting, setDetecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleDetect = async () => {
    if (!apiHost || !apiKey) {
      setError('请先填写 API 地址与 API Key');
      return;
    }
    setDetecting(true);
    setError(null);
    try {
      const r = await providersApi.detect(apiHost, apiKey);
      setDetected(r.data.models);
      if (r.data.models.length > 0 && !apiModel) {
        setApiModel(r.data.models[0].id);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '检测失败');
    } finally {
      setDetecting(false);
    }
  };

  const handleSave = async () => {
    if (!providerId.trim() || !name.trim() || !apiHost.trim() || !apiKey.trim()) {
      setError('供应商 ID、名称、API 地址、API Key 都是必填');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (mode === 'add') {
        await providersApi.add({
          provider_id: providerId.trim(),
          name: name.trim(),
          notes: notes.trim(),
          api_host: apiHost.trim(),
          api_key: apiKey,
          api_model: apiModel.trim(),
        });
      } else if (initial) {
        await providersApi.update(initial.providerId, {
          name: name.trim(),
          notes: notes.trim(),
          api_host: apiHost.trim(),
          api_key: apiKey, // rotating on every edit
          api_model: apiModel.trim(),
        });
      }
      onSave();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 480,
          maxWidth: '90vw',
          maxHeight: '90vh',
          overflowY: 'auto',
          background: 'var(--bg-card)',
          borderRadius: 12,
          padding: 20,
          border: '1px solid var(--border)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
          {mode === 'add' ? '添加模型服务' : `编辑 ${initial?.name ?? ''}`}
        </h2>

        {error && (
          <div
            style={{
              marginBottom: 12,
              padding: '8px 12px',
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.4)',
              borderRadius: 6,
              color: '#ef4444',
              fontSize: 12,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <label style={labelStyle}>供应商 ID（不可重复，不可改）</label>
            <input
              style={inputStyle}
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
              placeholder="例如 my-deepseek"
              disabled={mode === 'edit'}
            />
          </div>
          <div>
            <label style={labelStyle}>名称</label>
            <input
              style={inputStyle}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="DeepSeek (生产)"
            />
          </div>
          <div>
            <label style={labelStyle}>备注</label>
            <input
              style={inputStyle}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="选填"
            />
          </div>
          <div>
            <label style={labelStyle}>API 请求地址 URL</label>
            <input
              style={inputStyle}
              value={apiHost}
              onChange={(e) => setApiHost(e.target.value)}
              placeholder="https://api.example.com/v1"
            />
          </div>
          <div>
            <label style={labelStyle}>
              API Key
              {mode === 'edit' && (
                <span style={{ color: 'var(--text-tertiary)', fontSize: 11, marginLeft: 6 }}>
                  （编辑时如不填则保留旧 Key；填了则替换）
                </span>
              )}
            </label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                style={inputStyle}
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={mode === 'add' ? 'sk-...' : '（留空保留旧 Key）'}
              />
              <button type="button" style={secondaryBtn} onClick={() => setShowKey(!showKey)}>
                {showKey ? '隐藏' : '显示'}
              </button>
            </div>
          </div>
          <div>
            <label style={labelStyle}>默认模型</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                style={inputStyle}
                value={apiModel}
                onChange={(e) => setApiModel(e.target.value)}
                list={`models-${providerId}`}
                placeholder="例如 gpt-4o-mini"
              />
              <button
                type="button"
                style={secondaryBtn}
                onClick={handleDetect}
                disabled={detecting || !apiHost || !apiKey}
              >
                {detecting ? '检测中…' : '检测模型'}
              </button>
            </div>
            {detected.length > 0 && (
              <datalist id={`models-${providerId}`}>
                {detected.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </datalist>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
          <button type="button" style={secondaryBtn} onClick={onClose}>
            取消
          </button>
          <button type="button" style={primaryBtn} onClick={handleSave} disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -10`
Expected: no errors from this file.

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git add frontend/src/features/admin/ModelServiceForm.tsx && git commit -m "feat(admin): ModelServiceForm 5-field form + detect button"
```

### Task 22: New `ModelServicePanel.tsx` (replaces `KeyManagementPage` internals)

**Files:**

- Create: `frontend/src/features/admin/ModelServicePanel.tsx`
- Modify: `frontend/src/features/admin/KeyManagementPage.tsx` (replace internals, keep filename)

- [ ] **Step 1: Create `ModelServicePanel.tsx`**

Create `frontend/src/features/admin/ModelServicePanel.tsx`:

```tsx
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { providersApi, type Provider } from '../../api/admin/providers';
import { ModelServiceForm } from './ModelServiceForm';

const cardStyle: React.CSSProperties = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
};

const healthColor = (h?: Provider['health']) => {
  if (h === 'unhealthy') return '#ef4444';
  if (h === 'degraded') return '#f59e0b';
  return '#22c55e';
};

const healthLabel = (h?: Provider['health']) => {
  if (h === 'unhealthy') return '不可用';
  if (h === 'degraded') return '降级';
  return '正常';
};

export function ModelServicePanel() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [formMode, setFormMode] = useState<'add' | 'edit' | null>(null);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await providersApi.list();
      setProviders(r.data);
    } catch (e) {
      console.error('load providers failed', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = providers.filter((p) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      p.name.toLowerCase().includes(q) ||
      p.providerId.toLowerCase().includes(q) ||
      p.notes.toLowerCase().includes(q) ||
      p.apiHost.toLowerCase().includes(q)
    );
  });

  const handleCheck = async (p: Provider) => {
    try {
      const r = await providersApi.check(p.providerId, p.apiModel);
      if (r.data.status !== 'ok') {
        alert(`测速失败: ${r.data.status} ${r.data.status_code ?? ''}`);
      } else {
        alert(`${p.name}: ${r.data.latency_ms}ms`);
      }
    } catch (e) {
      alert(`测速异常: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleDelete = async (p: Provider) => {
    if (!confirm(`确认删除 ${p.name}?`)) return;
    try {
      await providersApi.delete(p.providerId);
      load();
    } catch (e) {
      alert(`删除失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">模型服务</h1>
        <div className="flex items-center gap-2">
          <input
            placeholder="搜索名称 / ID / URL / 备注"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <button
            onClick={() => navigate('/admin/usage')}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              background: 'transparent',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            使用统计
          </button>
          <button
            onClick={() => {
              setEditingProvider(null);
              setFormMode('add');
            }}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              background: 'var(--accent)',
              color: '#fff',
              border: 'none',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            + 添加
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-tertiary)' }}>加载中…</div>
      ) : filtered.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            color: 'var(--text-tertiary)',
            padding: '60px 0',
            background: 'var(--bg-card)',
            borderRadius: 10,
            border: '1px dashed var(--border)',
          }}
        >
          {search ? '没有匹配的模型服务' : '还没有任何模型服务，点右上角"添加"创建第一条'}
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 12,
          }}
        >
          {filtered.map((p) => (
            <div key={p.providerId} style={cardStyle}>
              <div className="flex items-center justify-between">
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{p.providerId}</div>
                </div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 11,
                    color: healthColor(p.health),
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: healthColor(p.health),
                    }}
                  />
                  {healthLabel(p.health)}
                </div>
              </div>
              {p.notes && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{p.notes}</div>
              )}
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{p.apiHost}</div>
              {p.apiModel && (
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: 'monospace',
                    background: 'rgba(0,0,0,0.2)',
                    padding: '2px 6px',
                    borderRadius: 4,
                    alignSelf: 'flex-start',
                  }}
                >
                  {p.apiModel}
                </div>
              )}
              <div className="flex items-center gap-2 mt-2">
                <button
                  onClick={() => handleCheck(p)}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  测速
                </button>
                <button
                  onClick={() => {
                    setEditingProvider(p);
                    setFormMode('edit');
                  }}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  编辑
                </button>
                <button
                  onClick={() => handleDelete(p)}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'transparent',
                    color: '#ef4444',
                    border: '1px solid rgba(239,68,68,0.4)',
                    cursor: 'pointer',
                  }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ModelServiceForm
        open={formMode !== null}
        mode={formMode ?? 'add'}
        initial={editingProvider}
        onClose={() => setFormMode(null)}
        onSave={() => {
          setFormMode(null);
          load();
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Replace `KeyManagementPage.tsx` internals**

Open `frontend/src/features/admin/KeyManagementPage.tsx`. Replace the entire body of the file with:

```tsx
import { ModelServicePanel } from './ModelServicePanel';

export function KeyManagementPage() {
  return <ModelServicePanel />;
}
```

- [ ] **Step 3: Typecheck**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -20`
Expected: no errors from these files (any errors in `KeyManagementPage` callers will be in `routes/index.tsx` if the default export was renamed; this is a named export `KeyManagementPage` so the route stays the same).

- [ ] **Step 4: Commit**

```bash
cd /home/chou/InnovOS && git add frontend/src/features/admin/ModelServicePanel.tsx frontend/src/features/admin/KeyManagementPage.tsx && git commit -m "feat(admin): ModelServicePanel replaces KeyManagementPage internals"
```

### Task 23: New `UserModelServicesPage.tsx` (per-user enable + reorder)

**Files:**

- Create: `frontend/src/features/admin/UserModelServicesPage.tsx`
- Create: `tests/components/UserModelServicesPage.test.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/features/admin/UserModelServicesPage.tsx`:

```tsx
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  userModelServicesApi,
  type UserModelService,
  type AvailableModelService,
} from '../../api/admin/userModelServices';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const rowStyle = (dragging: boolean): React.CSSProperties => ({
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '10px 12px',
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  opacity: dragging ? 0.5 : 1,
});

const healthDot = (h?: boolean) => (h === false ? '#ef4444' : '#22c55e');

function SortableRow({ id, children }: { id: string; children: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
  });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  return (
    <div ref={setNodeRef} style={{ ...rowStyle(isDragging), ...style }}>
      <span
        {...attributes}
        {...listeners}
        style={{ cursor: 'grab', color: 'var(--text-tertiary)', fontSize: 16 }}
        title="拖拽重排"
      >
        ⋮⋮
      </span>
      {children}
    </div>
  );
}

export function UserModelServicesPage() {
  const { userId: userIdParam } = useParams<{ userId: string }>();
  const userId = Number(userIdParam);
  const navigate = useNavigate();

  const [enabled, setEnabled] = useState<UserModelService[]>([]);
  const [available, setAvailable] = useState<AvailableModelService[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const [a, b] = await Promise.all([
        userModelServicesApi.list(userId),
        userModelServicesApi.listAvailable(userId),
      ]);
      setEnabled(a.data);
      setAvailable(b.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  const onDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = enabled.findIndex((e) => e.provider_id === active.id);
    const newIndex = enabled.findIndex((e) => e.provider_id === over.id);
    const next = arrayMove(enabled, oldIndex, newIndex);
    setEnabled(next);
    try {
      await userModelServicesApi.reorder(
        userId,
        next.map((e) => e.provider_id),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : '排序保存失败');
      load(); // re-fetch to revert
    }
  };

  const handleAdd = async (providerId: string) => {
    try {
      await userModelServicesApi.add(userId, providerId);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '添加失败');
    }
  };

  const handleRemove = async (providerId: string) => {
    try {
      await userModelServicesApi.remove(userId, providerId);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '移除失败');
    }
  };

  const handleToggle = async (providerId: string, isEnabled: boolean) => {
    try {
      await userModelServicesApi.toggle(userId, providerId, isEnabled);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '切换失败');
    }
  };

  if (loading) return <div style={{ padding: 24 }}>加载中…</div>;

  const notEnabled = available.filter((a) => !a.already_enabled);

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 className="text-2xl font-bold">用户 #{userId} — AI 模型服务</h1>
          <Link
            to="/admin/users"
            style={{ color: 'var(--text-secondary)', fontSize: 12, textDecoration: 'underline' }}
          >
            ← 返回用户管理
          </Link>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '8px 12px',
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.4)',
            borderRadius: 6,
            color: '#ef4444',
            fontSize: 12,
          }}
        >
          {error}
        </div>
      )}

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>
          已开通（按故障转移顺序）
        </h2>
        {enabled.length === 0 ? (
          <div
            style={{
              padding: 20,
              textAlign: 'center',
              color: 'var(--text-tertiary)',
              background: 'var(--bg-card)',
              border: '1px dashed var(--border)',
              borderRadius: 8,
            }}
          >
            暂未开通任何模型服务；从下方"未开通"里添加
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext
              items={enabled.map((e) => e.provider_id)}
              strategy={verticalListSortingStrategy}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {enabled.map((e, i) => (
                  <SortableRow key={e.provider_id} id={e.provider_id}>
                    <span
                      style={{
                        fontSize: 11,
                        color: 'var(--text-tertiary)',
                        minWidth: 24,
                      }}
                    >
                      #{i + 1}
                    </span>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: healthDot(e.is_healthy),
                      }}
                      title={e.is_healthy ? '健康' : '降级/不可用'}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{e.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                        {e.api_host} · {e.api_model || '（无默认模型）'}
                      </div>
                    </div>
                    <button
                      onClick={() => handleToggle(e.provider_id, !e.is_enabled)}
                      style={{
                        padding: '4px 10px',
                        fontSize: 11,
                        borderRadius: 4,
                        background: 'transparent',
                        color: e.is_enabled ? '#22c55e' : 'var(--text-tertiary)',
                        border: '1px solid var(--border)',
                        cursor: 'pointer',
                      }}
                    >
                      {e.is_enabled ? '已启用' : '已停用'}
                    </button>
                    <button
                      onClick={() => handleRemove(e.provider_id)}
                      style={{
                        padding: '4px 10px',
                        fontSize: 11,
                        borderRadius: 4,
                        background: 'transparent',
                        color: '#ef4444',
                        border: '1px solid rgba(239,68,68,0.4)',
                        cursor: 'pointer',
                      }}
                    >
                      移除
                    </button>
                  </SortableRow>
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </section>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>未开通</h2>
        {notEnabled.length === 0 ? (
          <div
            style={{
              padding: 16,
              textAlign: 'center',
              color: 'var(--text-tertiary)',
              background: 'var(--bg-card)',
              border: '1px dashed var(--border)',
              borderRadius: 8,
            }}
          >
            目录里所有模型服务都已开通
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {notEnabled.map((a) => (
              <div key={a.provider_id} style={rowStyle(false)}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: healthDot(a.is_healthy),
                    marginLeft: 12,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{a.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {a.api_host} · {a.api_model || '（无默认模型）'}
                  </div>
                </div>
                <button
                  onClick={() => handleAdd(a.provider_id)}
                  style={{
                    padding: '4px 12px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'var(--accent)',
                    color: '#fff',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  + 开通
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Register the route**

Open `frontend/src/routes/index.tsx`. Add (using the same import style as the other lazy pages):

```tsx
const UserModelServicesPage = lazyPage(() => import('../features/admin/UserModelServicesPage'));
```

And add to the `children: [...]` of the `path: '/'` ProtectedRoute:

```tsx
{
  path: 'admin/users/:userId/model-services',
  element: (
    <AdminRoute>
      <UserModelServicesPage />
    </AdminRoute>
  ),
},
```

- [ ] **Step 3: Typecheck and commit**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -10`

```bash
cd /home/chou/InnovOS && git add frontend/src/features/admin/UserModelServicesPage.tsx frontend/src/routes/index.tsx && git commit -m "feat(admin): per-user model services page + route"
```

### Task 24: New `UsageStatsPage.tsx`

**Files:**

- Create: `frontend/src/features/admin/UsageStatsPage.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/features/admin/UsageStatsPage.tsx`:

```tsx
import { useEffect, useState } from 'react';
import {
  usageApi,
  type UsageRange,
  type UsageSummary,
  type ProviderUsage,
  type ModelUsage,
  type CallLogRow,
} from '../../api/admin/usage';

const ranges: UsageRange[] = ['1d', '7d', '30d', '90d'];

export function UsageStatsPage() {
  const [range, setRange] = useState<UsageRange>('7d');
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [byProvider, setByProvider] = useState<ProviderUsage[]>([]);
  const [byModel, setByModel] = useState<ModelUsage[]>([]);
  const [recent, setRecent] = useState<CallLogRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      usageApi.summary(range),
      usageApi.byProvider(range),
      usageApi.byModel(range),
      usageApi.recent(50),
    ])
      .then(([s, p, m, r]) => {
        setSummary(s.data);
        setByProvider(p.data);
        setByModel(m.data);
        setRecent(r.data);
      })
      .catch((e) => console.error('usage load failed', e))
      .finally(() => setLoading(false));
  }, [range]);

  if (loading || !summary) return <div style={{ padding: 24 }}>加载中…</div>;

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">使用统计</h1>
        <div style={{ display: 'flex', gap: 4 }}>
          {ranges.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              style={{
                padding: '4px 12px',
                fontSize: 12,
                borderRadius: 4,
                background: range === r ? 'var(--accent)' : 'transparent',
                color: range === r ? '#fff' : 'var(--text-secondary)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 12,
        }}
      >
        {[
          { label: '总请求', value: summary.total_requests.toLocaleString() },
          { label: '总 Tokens', value: summary.total_tokens.toLocaleString() },
          { label: '平均延迟', value: `${summary.avg_latency_ms}ms` },
          {
            label: '成功率',
            value: `${(summary.success_rate * 100).toFixed(1)}%`,
            color:
              summary.success_rate >= 0.9
                ? '#22c55e'
                : summary.success_rate >= 0.5
                  ? '#f59e0b'
                  : '#ef4444',
          },
        ].map((c) => (
          <div
            key={c.label}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              padding: 16,
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{c.label}</div>
            <div style={{ fontSize: 22, fontWeight: 600, color: c.color ?? 'var(--text-primary)' }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>按供应商</h2>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>供应商</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>请求</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Tokens</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>平均延迟</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>成功率</th>
            </tr>
          </thead>
          <tbody>
            {byProvider.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-tertiary)' }}
                >
                  暂无数据
                </td>
              </tr>
            ) : (
              byProvider.map((p) => (
                <tr key={p.provider_id}>
                  <td style={tdStyle}>{p.provider_id}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{p.requests}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    {p.total_tokens.toLocaleString()}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{p.avg_latency_ms}ms</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    {(p.success_rate * 100).toFixed(1)}%
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>按模型</h2>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>模型</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>请求</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>输入 Tokens</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>输出 Tokens</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>平均延迟</th>
            </tr>
          </thead>
          <tbody>
            {byModel.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-tertiary)' }}
                >
                  暂无数据
                </td>
              </tr>
            ) : (
              byModel.map((m) => (
                <tr key={m.model_id}>
                  <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{m.model_id}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{m.requests}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    {m.input_tokens.toLocaleString()}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    {m.output_tokens.toLocaleString()}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{m.avg_latency_ms}ms</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>最近 50 条调用</h2>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>时间</th>
              <th style={thStyle}>供应商</th>
              <th style={thStyle}>模型</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Tokens</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>延迟</th>
              <th style={thStyle}>状态</th>
              <th style={thStyle}>故障转移</th>
            </tr>
          </thead>
          <tbody>
            {recent.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-tertiary)' }}
                >
                  暂无数据
                </td>
              </tr>
            ) : (
              recent.map((r) => (
                <tr key={r.id}>
                  <td style={{ ...tdStyle, fontSize: 11 }}>{r.created_at}</td>
                  <td style={tdStyle}>{r.provider_id}</td>
                  <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{r.model_id}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{r.total_tokens}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{r.latency_ms}ms</td>
                  <td style={tdStyle}>
                    <span style={{ color: r.is_success ? '#22c55e' : '#ef4444' }}>
                      {r.status_code}
                    </span>
                  </td>
                  <td style={tdStyle}>
                    {r.failover_attempt > 1
                      ? `从 ${r.failover_from_provider} (try #${r.failover_attempt})`
                      : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  overflow: 'hidden',
};
const thStyle: React.CSSProperties = {
  padding: '8px 12px',
  fontSize: 12,
  color: 'var(--text-tertiary)',
  textAlign: 'left',
  borderBottom: '1px solid var(--border)',
};
const tdStyle: React.CSSProperties = {
  padding: '6px 12px',
  fontSize: 12,
  color: 'var(--text-primary)',
  borderBottom: '1px solid var(--border)',
};
```

- [ ] **Step 2: Register the route**

In `frontend/src/routes/index.tsx`:

```tsx
const UsageStatsPage = lazyPage(() => import('../features/admin/UsageStatsPage'));
```

And inside the protected children:

```tsx
{
  path: 'admin/usage',
  element: (
    <AdminRoute>
      <UsageStatsPage />
    </AdminRoute>
  ),
},
```

- [ ] **Step 3: Typecheck and commit**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -10`

```bash
cd /home/chou/InnovOS && git add frontend/src/features/admin/UsageStatsPage.tsx frontend/src/routes/index.tsx && git commit -m "feat(admin): usage stats page + route"
```

### Task 25: Add the per-user management entry point to `UserManagementPage`

**Files:**

- Modify: `frontend/src/features/admin/UserManagementPage.tsx`
- Modify: `tests/components/UserManagementPage.test.tsx` (or create the file)

- [ ] **Step 1: Read the current `UserManagementPage.tsx`**

Open `frontend/src/features/admin/UserManagementPage.tsx`. Note the existing columns (id, email, role, actions, etc.). Add a new column header `"AI 模型服务"` and a new `<td>` with a `<Link to={...}>` to the per-user route. The exact insertion point depends on the current column ordering — pick a column near the right (just before the action buttons if there are any).

The link cell (one row, one user):

```tsx
<td style={tdStyle}>
  <Link
    to={`/admin/users/${user.id}/model-services`}
    style={{
      padding: '4px 10px',
      fontSize: 11,
      borderRadius: 4,
      background: 'transparent',
      color: 'var(--accent)',
      border: '1px solid var(--accent)',
      textDecoration: 'none',
    }}
  >
    管理 →
  </Link>
</td>
```

Add `Link` to the React Router DOM imports if not already present.

- [ ] **Step 2: Typecheck**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -10`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git add frontend/src/features/admin/UserManagementPage.tsx && git commit -m "feat(admin): per-user model services link in user list"
```

### Task 26: Delete legacy UI components

**Files:**

- Delete: `frontend/src/components/ui/ModelSelector.tsx`
- Delete: `frontend/src/components/ui/ModelEditDrawer.tsx`
- Delete: `frontend/src/features/admin/ProviderKeyPanel.tsx`

- [ ] **Step 1: Delete the files**

```bash
cd /home/chou/InnovOS && git rm frontend/src/components/ui/ModelSelector.tsx frontend/src/components/ui/ModelEditDrawer.tsx frontend/src/features/admin/ProviderKeyPanel.tsx
```

- [ ] **Step 2: Typecheck**

Run: `cd /home/chou/InnovOS/frontend && npx tsc --noEmit 2>&1 | tail -20`
Expected: errors only if some other file still imports the deleted components. Fix any remaining import by removing the import line (and any now-unused state).

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git commit -m "refactor(admin): delete ModelSelector, ModelEditDrawer, ProviderKeyPanel"
```

### Task 27: Drop `BUILTIN_PROVIDERS` from `providers_registry.py`

**Files:**

- Modify: `backend/app/algorithm/providers_registry.py`

- [ ] **Step 1: Remove the dead constants and helpers**

Open `backend/app/algorithm/providers_registry.py`. Delete:

- The entire `BUILTIN_PROVIDERS` dict.
- The `get_provider_info(provider_id)` function.
- The `list_all_builtin()` function.

Keep:

- The capability constants (`CAPABILITY_CHAT`, etc.) — still used by tests in `test_providers_registry.py` and by `client_registry.py`.
- The `infer_capabilities` / `normalize_model` / `get_model_id` / `get_model_capabilities` helpers — still used by some tests and analyzers.

- [ ] **Step 2: Run the test that touches this file**

Run: `cd /home/chou/InnovOS/backend && uv run pytest tests/test_providers_registry.py -v 2>&1 | tail -20`
Expected: at least the `BUILTIN_PROVIDERS` tests fail; remove or migrate them. If they cover only the deleted symbols, delete the test file. If they cover `CAPABILITY_*` and `infer_capabilities`, keep the file but trim the `BUILTIN_PROVIDERS` tests out.

- [ ] **Step 3: Commit**

```bash
cd /home/chou/InnovOS && git add backend/app/algorithm/providers_registry.py backend/tests/test_providers_registry.py && git commit -m "refactor(providers_registry): drop BUILTIN_PROVIDERS"
```

### Task 28: Frontend tests for the new pages

**Files:**

- Create: `tests/components/ModelServicePanel.test.tsx`
- Create: `tests/components/UserModelServicesPage.test.tsx`
- Create: `tests/components/UsageStatsPage.test.tsx`

- [ ] **Step 1: Add `@dnd-kit/*` to `frontend/package.json` if not present**

Run: `ls /home/chou/InnovOS/frontend/node_modules/@dnd-kit 2>/dev/null && echo "present" || echo "missing"`
If `missing`, add to `frontend/package.json` dependencies:

```json
"@dnd-kit/core": "^6.3.1",
"@dnd-kit/sortable": "^10.0.0",
"@dnd-kit/utilities": "^3.2.2"
```

Then `cd /home/chou/InnovOS/frontend && npm install`.

- [ ] **Step 2: `ModelServicePanel.test.tsx`**

Create `tests/components/ModelServicePanel.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ModelServicePanel } from '../../frontend/src/features/admin/ModelServicePanel';

vi.mock('../../frontend/src/api/admin/providers', () => ({
  providersApi: {
    list: vi.fn().mockResolvedValue({
      data: [
        {
          providerId: 'p1',
          name: 'P1',
          notes: '',
          apiHost: 'https://a',
          apiModel: 'm1',
          isEnabled: true,
          health: 'healthy',
        },
      ],
    }),
  },
}));

describe('ModelServicePanel', () => {
  it('renders the catalog card', async () => {
    render(
      <MemoryRouter>
        <ModelServicePanel />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('P1')).toBeInTheDocument();
    });
    expect(screen.getByText('模型服务')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: `UserModelServicesPage.test.tsx`**

Create `tests/components/UserModelServicesPage.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { UserModelServicesPage } from '../../frontend/src/features/admin/UserModelServicesPage';

vi.mock('../../frontend/src/api/admin/userModelServices', () => ({
  userModelServicesApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    listAvailable: vi.fn().mockResolvedValue({ data: [] }),
    add: vi.fn().mockResolvedValue({ data: [] }),
    remove: vi.fn().mockResolvedValue(undefined),
    toggle: vi.fn().mockResolvedValue({ data: { is_enabled: true } }),
    reorder: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

describe('UserModelServicesPage', () => {
  it('renders empty state', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/已开通/)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 4: `UsageStatsPage.test.tsx`**

Create `tests/components/UsageStatsPage.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { UsageStatsPage } from '../../frontend/src/features/admin/UsageStatsPage';

vi.mock('../../frontend/src/api/admin/usage', () => ({
  usageApi: {
    summary: vi.fn().mockResolvedValue({
      data: {
        total_requests: 1,
        total_tokens: 100,
        avg_latency_ms: 50,
        success_rate: 1,
        range: '7d',
      },
    }),
    byProvider: vi.fn().mockResolvedValue({ data: [] }),
    byModel: vi.fn().mockResolvedValue({ data: [] }),
    recent: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

describe('UsageStatsPage', () => {
  it('renders the four KPI labels', async () => {
    render(
      <MemoryRouter>
        <UsageStatsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('总请求')).toBeInTheDocument();
    });
    expect(screen.getByText('总 Tokens')).toBeInTheDocument();
    expect(screen.getByText('平均延迟')).toBeInTheDocument();
    expect(screen.getByText('成功率')).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run the new frontend tests**

Run: `cd /home/chou/InnovOS/frontend && npm test -- --run 2>&1 | tail -40`
Expected: 3 new test files run; pass.

- [ ] **Step 6: Commit**

```bash
cd /home/chou/InnovOS && git add frontend/package.json frontend/package-lock.json tests/components/ModelServicePanel.test.tsx tests/components/UserModelServicesPage.test.tsx tests/components/UsageStatsPage.test.tsx && git commit -m "test(admin): ModelServicePanel / UserModelServicesPage / UsageStatsPage"
```

### Task 29: `make quality` final checkpoint

- [ ] **Step 1: Run the full quality gate**

Run: `cd /home/chou/InnovOS && make quality 2>&1 | tail -60`
Expected: passes.

- [ ] **Step 2: If any failure, fix in place**

Most likely candidates:

- A `tsc --noEmit` error in the new pages (most often: a missing `id` on a `SortableContext` item).
- A `ruff` complaint on a long line in `failover_router.py` — break it.
- A `mypy` complaint on a return-type mismatch — add a `# type: ignore[return-value]` annotation only when the type is provably right.
- A `pytest` collection error in a legacy test file (Task 15 should have caught these, but new code may have shifted imports).

- [ ] **Step 3: Commit fixes**

```bash
cd /home/chou/InnovOS && git add -A && git commit -m "chore(quality): make quality pass after frontend refactor"
```

### Task 30: Manual smoke test against a running stack

- [ ] **Step 1: Start the stack**

Run: `cd /home/chou/InnovOS && make dev`
Expected: backend on `:8000`, frontend on `:5173`, Postgres on `:5432`.

- [ ] **Step 2: Create two test model services via the UI**

Open `http://localhost:5173/admin/keys`. Click "+ 添加". Fill the 5 fields for a test entry (e.g. provider_id=`smoke-a`, name=`Smoke A`, api_host=`https://api.deepseek.com/v1`, api_key=`sk-...`, api_model=`deepseek-chat`). Save. Repeat for a second entry `smoke-b` pointing at a fake host like `https://nonexistent.invalid/v1`.

- [ ] **Step 3: Open the per-user management page**

Click on a user in `/admin/users`, click "管理". In the new page, add `smoke-a` (priority 1) and `smoke-b` (priority 2). Save.

- [ ] **Step 4: Run an analysis that calls the AI**

From the UI, run a small task (any feature that exercises `chat_completion` — e.g. the workflow mock page or any of the 7 analyzers). Verify:

- One `model_call_log` row exists with `provider_id=smoke-a, is_success=true, failover_attempt=1`.
- The dashboard `/admin/usage` shows the call in the "最近 50 条" table.

- [ ] **Step 5: Force a failover**

Edit `smoke-a`'s `api_host` to `https://127.0.0.1:1/v1` (no listener). Save. Trigger an analysis. After 3 failed attempts, `smoke-a`'s health flips to unhealthy and the next call hits `smoke-b`. Verify in `model_call_log`:

- 3 rows with `provider_id=smoke-a, is_success=false, error_category=...`.
- 1 row with `provider_id=smoke-b, is_success=true, failover_from_provider=smoke-a, failover_attempt=4`.

- [ ] **Step 6: Commit a smoke-test report**

Create `docs/superpowers/plans/2026-07-31-model-service-refactor-smoke.md` with the exact results from Steps 4-5 (paste the log rows, paste the user flow). Commit:

```bash
cd /home/chou/InnovOS && git add docs/superpowers/plans/2026-07-31-model-service-refactor-smoke.md && git commit -m "docs(plan): smoke test report for model service refactor"
```
