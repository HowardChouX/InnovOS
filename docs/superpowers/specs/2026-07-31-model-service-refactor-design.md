# Model Service Refactor — Design

**Date:** 2026-07-31
**Status:** Pending user review (brainstorming complete)
**Author:** Codex (brainstorming skill)
**Scope:** InnovOS sidebar "模型服务" module + per-user failover queue (frontend + backend)

## Problem

The current sidebar entry "模型服务" (route `/admin/keys`, page
`KeyManagementPage.tsx`, ~1464 lines) has accumulated complexity that does not
match the user's actual need:

1. **7 hard-coded "BUILTIN" providers** (`deepseek`, `silicon`, `dashscope`,
   `openai`, `zhipu`, `moonshot`, `ollama`) in
   `backend/app/algorithm/providers_registry.py:BUILTIN_PROVIDERS` make the
   admin UI start with a fixed catalog that cannot be deleted. User wants
   **custom-only**.
2. **Per-provider multi-key rotation** (`ProviderKeyPool.lease_key()` in
   `ai_client.py`) is the wrong abstraction. User wants each model service
   entry to be a self-contained config (URL + 1 Key + default model) — no
   round-robin, no priority list within one provider.
3. **No per-user failover queue.** The current `model_runtime.py` /
   `model_resolver.py` resolves `providerId:modelId` to a single ModelConfig;
   a Provider being 5xx-down fails the entire request. User wants
   CC-Switch-style list-based failover: per-user ordered queue, on failure
   try next.
4. **No call-level usage log.** Only `api_keys.success_count / failure_count`
   are tracked. User wants per-call records (tokens, latency, status,
   failover chain).
5. **Heavy UI surface** (5 sub-components: `ProviderKeyPanel`, `ModelSelector`,
   `ModelEditDrawer`, `RagGlobalConfig`, plus the global "model assignment"
   block) is not part of what the user asked for. The user only wants the
   model service catalog + per-user access management + usage stats.

## Goal

Refactor (not rewrite) the sidebar "模型服务" entry into a focused module:

- A **flat list of "model service" entries** (rows in `model_providers`),
  each a self-contained config: `name / notes / api_host / api_key /
api_model` (default model). Entries can repeat (same URL, different
  `name`).
- **Per-user enable-and-order** via a new `user_model_services` table —
  admin decides which entries each user can use and in what order.
- **Failover queue per user**, evaluated at request time. On 3 consecutive
  failures (5xx/timeout/auth) within the circuit-breaker window, skip the
  failing entry for 5 minutes and try the next enabled entry.
- **Per-call usage log** (`model_call_log`) feeding an admin
  "使用统计" view (KPIs + per-provider table + per-model table + recent
  log list).
- **UI rebuilt to match CC Switch's `ProviderList` visual idiom** for the
  catalog page, and the existing UserManagementPage gets a new column
  linking to a per-user management route.

Non-goals (kept untouched):

- Knowledge-base / RAG configuration stays where it is.
- Analyzer pipeline internal signatures stay similar — only the AI client
  call shape changes.
- The existing 7 BUILTIN_PROVIDERS are dropped from code paths; old rows
  in `model_providers` are kept (admin can delete manually).
- `api_keys` table stays; the rotation/priority columns are no longer
  used by the runtime, but the encrypted-key infrastructure is reused
  (1 key per model service, `priority=0, name='default'`).
- Sidebar.tsx entry label and path stay identical: "模型服务" → `/admin/keys`.

## Design Decisions (locked with user)

1. **`api_keys` table**: keep. Each model service row has exactly 1
   `api_keys` row (priority=0, name='default'), inserted/updated
   automatically by the `POST /api/admin/providers` and
   `PUT /api/admin/providers/{pid}` handlers. No multi-key UI.
2. **Failover trigger**: 3 consecutive failures on the same model service
   entry flip `provider_health.is_healthy=false` and set
   `cooldown_until = NOW() + 5min`. While in cooldown, the entry is
   skipped. After cooldown expires, the entry gets another attempt;
   if it succeeds, the circuit closes and the counter resets. Matches
   CC Switch defaults.
3. **Usage log retention**: permanent by default; a daily 03:00 background
   task deletes rows older than 90 days. Configurable via
   `MODEL_CALL_LOG_RETENTION_DAYS` env var.
4. **Per-user model service management entry point**: a new column/button
   "AI 模型服务" in the existing `UserManagementPage` rows that links to
   a new independent route `/admin/users/{user_id}/model-services` (a
   new page that owns the per-user enable / order / toggle / health
   surface).
5. **File names**: `KeyManagementPage.tsx` is kept as the filename for
   the model service catalog page (it is heavily referenced by routes
   and tests). Internal content is replaced.

## Data Model

### Existing table — `model_providers` (delta)

Add one column; stop writing to two:

```sql
-- Added
ALTER TABLE model_providers ADD COLUMN notes TEXT NOT NULL DEFAULT '';
```

The `api_host` column already exists and stores the API URL. The
`api_model` column already exists and stores the default model. The
`api_keys` table already exists and stores the encrypted key (one row
per `model_providers` row, `priority=0`).

The legacy `models` JSON column and `max_rpm` column stay on disk
(this refactor does not touch the column DDL); only the application
code stops writing to them. A follow-up migration after this refactor
lands may drop them.

### New table — `provider_health`

Per-provider circuit-breaker state. Single row per provider (health is
provider-level, not per-user; if DeepSeek is down it's down for every
user).

```sql
CREATE TABLE provider_health (
    provider_id          TEXT PRIMARY KEY
                          REFERENCES model_providers(provider_id)
                          ON DELETE CASCADE,
    is_healthy           BOOLEAN NOT NULL DEFAULT TRUE,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_success_at      TIMESTAMPTZ,
    last_failure_at      TIMESTAMPTZ,
    cooldown_until       TIMESTAMPTZ,
    last_error_code      VARCHAR(64),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### New table — `user_model_services`

Per-user enable + failover queue. This is the core of the new feature.

```sql
CREATE TABLE user_model_services (
    user_id        BIGINT NOT NULL
                      REFERENCES users(id) ON DELETE CASCADE,
    provider_id    TEXT NOT NULL
                      REFERENCES model_providers(provider_id) ON DELETE CASCADE,
    failover_order INTEGER NOT NULL CHECK (failover_order >= 1),
    is_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, provider_id),
    UNIQUE (user_id, failover_order)
);
CREATE INDEX ix_ums_user_enabled
    ON user_model_services (user_id, is_enabled, failover_order);
```

Notes:

- `failover_order` is 1-based; 1 is tried first.
- Unique on `(user_id, failover_order)` so re-ordering is a swap-style
  operation (admin sets the new order; backend enforces no collisions).
- `is_enabled` lets admin pause an entry without removing it from the
  queue.

### New table — `model_call_log`

One row per call, with `failover_attempt` and `failover_from_provider`
capturing the failover chain. Indexed for the four stats queries.

```sql
CREATE TABLE model_call_log (
    id                    BIGSERIAL PRIMARY KEY,
    user_id               BIGINT REFERENCES users(id) ON DELETE SET NULL,
    provider_id           TEXT NOT NULL,
    model_id              TEXT NOT NULL,
    purpose               VARCHAR(32) NOT NULL DEFAULT 'chat',
    input_tokens          INTEGER NOT NULL DEFAULT 0,
    output_tokens         INTEGER NOT NULL DEFAULT 0,
    total_tokens          INTEGER NOT NULL DEFAULT 0,
    latency_ms            INTEGER NOT NULL DEFAULT 0,
    status_code           SMALLINT NOT NULL,
    is_success            BOOLEAN NOT NULL,
    error_category        VARCHAR(32),
    error_message         TEXT,
    is_streaming          BOOLEAN NOT NULL DEFAULT FALSE,
    failover_from_provider TEXT,
    failover_attempt      SMALLINT NOT NULL DEFAULT 1,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_mcl_provider_time ON model_call_log (provider_id, created_at DESC);
CREATE INDEX ix_mcl_user_time    ON model_call_log (user_id,    created_at DESC);
CREATE INDEX ix_mcl_model_time   ON model_call_log (model_id,   created_at DESC);
CREATE INDEX ix_mcl_time         ON model_call_log (created_at DESC);
```

A new Alembic revision `0017_add_user_model_services_and_call_log.py`
creates the three new tables and adds the `notes` column. The existing
`0016_create_models.py` is left alone (the `models` table keeps its
current shape; only the JS UI stops reading it).

## Backend Changes

### Files deleted

- `backend/app/algorithm/model_runtime.py` — composite-ID resolution is
  replaced by per-user queue lookup.
- `backend/app/algorithm/model_registry.py` — `models.json` registry is
  no longer the source of truth; entries are stored in
  `model_providers`.
- `backend/app/algorithm/models_crud.py` — model-metadata CRUD is gone.

### Files modified

- `backend/app/algorithm/providers_registry.py` — drop
  `BUILTIN_PROVIDERS` dict, `list_all_builtin()`, `get_provider_info()`.
  Keep `CAPABILITY_*` constants and `normalize_model()` helpers for any
  remaining callers; if no callers remain, delete those too in a
  follow-up.
- `backend/app/algorithm/ai_client.py` — strip `ProviderKeyPool` and the
  rich `CallOutcome` error classification table. Add a
  `chat_completion(*, user_id, purpose, messages, ...)` entry point
  that calls into the new `FailoverRouter` (see below) and returns the
  same shape `analyzers` expect today.
- `backend/app/algorithm/base.py` — 7 analyzers and the pipeline update
  their call sites from `ModelRuntime.resolve(...)` /
  `ModelResolver.resolve_for_purpose(...)` to
  `chat_completion(user_id=current_user.id, purpose='chat', messages=...)`.
  The `KnowledgeJob` workers also need the same change.
- `backend/app/algorithm/model_service.py` — collapse to a thin class:
  `list_all() / get(provider_id) / upsert(data) / delete(provider_id) /
detect_models(provider_id) / check_connection(provider_id)`. The
  `upsert` path writes both the `model_providers` row and a single
  `api_keys` row (`priority=0, name='default'`, ciphertext from
  `ApiKeyService.create_key()` or `replace_secret()`). On delete, the
  cascade removes the `api_keys` row and the `provider_health` row.
- `backend/app/api/admin/providers.py` — simplify Pydantic models
  (`AddProviderInput` = `{provider_id, name, notes, api_host, api_key,
default_model}`, `UpdateProviderInput` = same fields all optional +
  `is_enabled`). Drop the entire `/keys/*` sub-router, `/builtin`,
  `/models/reconcile*`, `/{pid}/models/{mid}`, `/{pid}/models/check`.
  Keep `/check` and `/detect-models`.
- `backend/app/api/admin/settings.py` — drop `/models/assigned*`,
  `/models/available`, `/rag/*`. If any of these are still used by
  non-refactored code (knowledge/embedder), keep them as deprecated
  no-ops returning empty data and add a TODO; otherwise delete.

### Files added

- `backend/app/services/failover_router.py` — the runtime heart of
  per-user failover. Public API:

  ```python
  class FailoverRouter:
      def __init__(self, db, api_key_service, usage_logger,
                   max_attempts: int = 4,
                   failure_threshold: int = 3,
                   cooldown_seconds: int = 300): ...

      async def call(
          self,
          *,
          user_id: int,
          purpose: str,
          messages: list[dict],
          model_override: str | None = None,
      ) -> ChatResult: ...
  ```

  Behavior:

  1. Load the user's enabled queue from `user_model_services` joined
     with `model_providers` and `provider_health`, ordered by
     `failover_order ASC`, with `cooldown_until IS NULL OR
cooldown_until <= NOW()` as a filter.
  2. For each entry in order, call `_call_one_provider(...)` which
     a) leases the 1 api_key for that provider,
     b) calls `OpenAICompatibleAdapter.chat(...)`,
     c) parses token counts from the response,
     d) updates `provider_health` (success → reset counter;
     failure → `consecutive_failures += 1`; on
     `>= failure_threshold`, set `is_healthy=false`,
     `cooldown_until=NOW()+cooldown_seconds`),
     e) returns success or failure to the loop.
  3. The loop stops on the first success or when
     `attempt >= max_attempts` (default 4 — covers P1 + P2 + P3 + P4
     before giving up).
  4. Each attempt writes one `model_call_log` row. The first attempt
     has `failover_from_provider=NULL`; subsequent attempts set it to
     the previous provider's `provider_id` and bump
     `failover_attempt`.
  5. If the queue is empty (user has no enabled entries), raise
     `NoProvidersConfiguredError` (re-use the existing error class).

- `backend/app/services/usage_logger.py` — encapsulates
  `model_call_log` inserts. One `record_call(...)` call per attempt.
  Async / fire-and-forget; failures are logged but never block the
  caller. (Mirrors how `usage_events.rs` works in CC Switch.)
- `backend/app/api/admin/user_model_services.py` — REST surface for the
  new independent route. Endpoints (all admin-gated):

  ```
  GET    /api/admin/users/{user_id}/model-services
         → 200 { data: [{ provider_id, name, api_host, default_model,
                          failover_order, is_enabled, health }, ...] }
  POST   /api/admin/users/{user_id}/model-services
         body: { provider_id }
         → 200 (appends at end of queue)
  DELETE /api/admin/users/{user_id}/model-services/{provider_id}
         → 204
  POST   /api/admin/users/{user_id}/model-services/{provider_id}/toggle
         body: { is_enabled: bool }
         → 200
  PUT    /api/admin/users/{user_id}/model-services/order
         body: { provider_ids: [pid_a, pid_b, ...] }
         → 200
  GET    /api/admin/users/{user_id}/model-services/available
         → 200 { data: [{ provider_id, name, api_host, default_model,
                          already_enabled: bool, health }, ...] }
  ```

  `PUT /order` is a swap-style operation: the backend assigns
  `failover_order = position_in_array` for the listed providers; any
  provider not in the array but currently in the queue is removed.

- `backend/app/api/admin/usage.py` — read-only stats surface:

  ```
  GET /api/admin/usage/summary
      ?range=7d&user_id=...
      → 200 { data: { total_requests, total_tokens, success_rate,
                      avg_latency_ms, range } }
  GET /api/admin/usage/by-provider
      ?range=7d&user_id=...
      → 200 { data: [{ provider_id, name, requests, total_tokens,
                       success_rate, avg_latency_ms }, ...] }
  GET /api/admin/usage/by-model
      ?range=7d&user_id=...
      → 200 { data: [{ model_id, requests, total_tokens,
                       success_rate, avg_latency_ms }, ...] }
  GET /api/admin/usage/recent
      ?limit=50&user_id=...
      → 200 { data: [model_call_log row, ...] }
  ```

  Range presets: `1d / 7d / 30d / 90d` (matches CC Switch's range
  picker). Optional `user_id` filter; default = all users (admin
  dashboard). All four queries are pure SQL aggregations against
  `model_call_log`; no caching layer needed for the v1.

- `backend/app/api/admin/failover.py` — admin global view of provider
  health:

  ```
  GET  /api/admin/failover/health
       → 200 { data: [{ provider_id, name, is_healthy,
                        consecutive_failures, cooldown_until,
                        last_error_code }, ...] }
  POST /api/admin/failover/{provider_id}/reset
       → 200 (clears cooldown, resets counter)
  ```

- `backend/app/services/usage_log_cleanup.py` — invoked by the
  existing `backup_service` daily cron (which already runs at 03:00)
  via a new scheduled job: `DELETE FROM model_call_log WHERE
created_at < NOW() - INTERVAL '90 days'`. Retention configurable
  via `MODEL_CALL_LOG_RETENTION_DAYS` env var.
- `backend/alembic/versions/0017_add_user_model_services_and_call_log.py`
  — Alembic migration creating the three new tables and adding
  `model_providers.notes`.

### Auth boundary

All `/api/admin/*` endpoints keep the existing `require_admin`
dependency. Per-user model service access is admin-managed (not
self-service); regular users do not see the catalog page and cannot
modify their own queue. The `FailoverRouter.call(...)` is the only
runtime entry point used by analyzers and accepts any authenticated
`user_id`; admins calling on behalf of other users is not a v1
feature.

## Frontend Changes

### Files modified

- `frontend/src/components/layout/Sidebar.tsx` — no changes. The
  "模型服务" link still points to `/admin/keys`. The "用户管理" link
  still points to `/admin/users`. (Decision 4: just add a link/column
  inside UserManagementPage that goes elsewhere; the sidebar itself is
  untouched.)
- `frontend/src/features/admin/KeyManagementPage.tsx` — keep filename
  (Decision 5). Internal content is replaced by the new
  ModelServicePanel (see below). Existing tests in
  `tests/components/KeyManagementPage.test.tsx` will be re-targeted
  to the new internal component name.
- `frontend/src/features/admin/UserManagementPage.tsx` — add a new
  column "AI 模型服务" with a button "管理" that links to
  `/admin/users/{user_id}/model-services`. Otherwise leave the user
  list alone.
- `frontend/src/api/admin/providers.ts` — replace the existing
  `Provider` type with the 5-field shape
  (`provider_id, name, notes, api_host, api_key, default_model`,
  with `isEnabled` and `health` as derived). Drop the
  `models / maxRpm / protocol / requestCount` fields.
- `frontend/src/api/admin/settings.ts` — delete the
  `getAssigned / setAssigned / getAvailable / getRagConfig /
setRagConfig` functions (or keep as deprecated no-ops if any
  knowledge/RAG code still imports them).
- `frontend/src/routes/index.tsx` — register the new
  `/admin/users/:userId/model-services` route.

### Files added

- `frontend/src/features/admin/ModelServicePanel.tsx` — the new
  catalog page. Visual model: CC Switch's `ProviderList`
  (sortable card grid + add/edit/delete + per-card
  health badge + measure button). The body holds:
  - A top toolbar: title "模型服务", count, search box, "添加"
    button, "使用统计" link to `/admin/usage`.
  - A card grid: each card shows
    `name / notes (truncated) / api_host / default_model / health
badge / enabled toggle / measure (测速) / edit / delete`. Cards
    are not user-ordered (the catalog is unordered; order is per
    user).
  - An "Add" / "Edit" modal with the 5 fields plus a "检测" button
    that hits a new `POST /api/admin/providers/detect` endpoint
    (accepts `api_host + api_key` and returns the upstream model
    list, so detect works before the row exists).
- `frontend/src/features/admin/ModelServiceForm.tsx` — the 5-field
  form. Reuses `ModelInputWithFetch`-style detect button from CC
  Switch (calls the new pre-create detect endpoint).
- `frontend/src/features/admin/UsageStatsPage.tsx` — the new
  `/admin/usage` page. KPI cards on top
  (`total_requests / total_tokens / success_rate / avg_latency_ms`),
  a per-provider table, a per-model table, a recent-calls table.
  Range picker (`1d / 7d / 30d / 90d`) and optional user filter.
- `frontend/src/features/admin/UserModelServicesPage.tsx` — the new
  `/admin/users/:userId/model-services` page. Two stacked sections:
  "已开通" (the user's queue, drag-and-drop to reorder, toggle to
  enable/disable, "移除" button) and "未开通" (the rest of the
  catalog, "+ 开通" button). Each row carries the provider's
  `provider_id, name, api_host, default_model, health`.
- `frontend/src/api/admin/userModelServices.ts` — typed wrapper
  for the new endpoints.
- `frontend/src/api/admin/usage.ts` — typed wrapper for the stats
  endpoints.
- `frontend/src/api/admin/failover.ts` — typed wrapper for the
  health-overview endpoints.

### Files deleted

- `frontend/src/components/ui/ModelSelector.tsx`
- `frontend/src/components/ui/ModelEditDrawer.tsx`
- `frontend/src/features/admin/ProviderKeyPanel.tsx`
- The `RagGlobalConfig` and `AssignedModels` blocks inside
  `KeyManagementPage.tsx`.

## Test Plan

Backend (pytest, all in `backend/tests/`):

- `test_failover_router.py` — happy path: user with 3 enabled
  entries, first succeeds, log row has `failover_attempt=1,
failover_from_provider=NULL`. Failure path: first entry's API
  returns 5xx three times → entry's `provider_health.is_healthy=
false` and `cooldown_until` is set; second call on the router
  skips that entry. Cooldown expiry returns the entry to the
  queue.
- `test_usage_log.py` — every call writes one row; the `usage_log`
  fire-and-forget task is awaited in tests; `failover_from_provider`
  is correct on attempt 2+; token counts are populated from the
  response.
- `test_user_model_services_api.py` — admin can add / remove /
  toggle / reorder. `PUT /order` with the same array twice is
  idempotent. Adding a duplicate raises 409. Removing a missing
  entry returns 204 (idempotent).
- `test_provider_health_api.py` — `GET /failover/health` returns
  the catalog + each row's health; `POST /reset` clears cooldown.
- `test_usage_api.py` — summary / by-provider / by-model / recent
  against a seeded log; range filter; user filter; zero-row
  graceful empty state.
- `test_model_service_api.py` — `POST /api/admin/providers` writes
  both `model_providers` and one `api_keys` row; `PUT` updates both;
  `DELETE` cascades. `notes` round-trips.

Frontend (vitest + RTL, all in `tests/`):

- `ModelServicePanel.test.tsx` — renders the catalog; add modal
  validates the 5 fields; detect button hits the right endpoint and
  populates `default_model`; delete confirmation.
- `UserModelServicesPage.test.tsx` — add / remove / toggle / drag-
  and-drop reorder; the PUT /order call payload matches the visible
  order.
- `UsageStatsPage.test.tsx` — KPIs render; range picker refetches;
  user filter narrows results.
- `UserManagementPage.test.tsx` — updated to assert the new
  "AI 模型服务" column link points to the right URL.

End-to-end (manual smoke test, no Playwright in this repo today):

- Admin adds model service A (DeepSeek) and B (OpenAI).
- Admin opens `/admin/users/{alice.id}/model-services`, adds A and
  B, orders A first.
- As alice, run an analysis; first request hits A; verify one
  `model_call_log` row with `provider_id=A`.
- Stop A's API (point `api_host` at a non-routable URL). After 3
  failed attempts, the router flips A's health and uses B. Verify
  a log row with `provider_id=B, failover_from_provider=A,
failover_attempt=2`.

## Quality Gates

- `make lint` (ESLint + Ruff + Prettier)
- `make typecheck` (tsc + mypy)
- `make test` (pytest --cov-fail-under=60 + vitest)
- `make format` must be a no-op after the implementation lands
- `make security` (bandit + npm audit) — no new findings

Per `AGENTS.md`, all five must pass locally before the work is
considered done. The `test_chat_completion_unified.py`,
`test_model_resolver.py`, `test_model_resolver_purpose.py`,
`test_model_runtime.py`, `test_model_registry.py`,
`test_providers_registry.py`, and `test_model_reconcile.py` tests
will all need updates or removals because they exercise the old
abstractions. They are explicitly listed in the implementation plan
so nothing is missed.

## Out of Scope (explicit non-goals)

- Knowledge base / RAG / embedding model wiring.
- The 7 analyzers' internal logic — only their AI-client call sites
  change.
- Self-service user signup of model services (only admin can
  enable).
- Web UI for editing `provider_health.cooldown_until` directly
  (only `POST /failover/{pid}/reset` is exposed).
- Multi-key within one model service entry. The `api_keys.priority`
  column is left in place but always set to 0 by the new upsert
  path.
- Dropping the legacy `models` JSON column on `model_providers` and
  the `models` table. Tracked as a follow-up after this refactor.
- Changing the analyzer pipeline's failure semantics beyond the
  new failover router's contract.

## Open Questions (none)

All design decisions were locked with the user before this spec
was written. The implementation plan produced by the
`writing-plans` skill will be a flat, ordered list of small tasks
mapped to these files.
