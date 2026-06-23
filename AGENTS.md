# InnovOS

**Stack:** Python FastAPI (backend) + React 19/Vite/TypeScript (frontend) + PostgreSQL (pgvector) + Tailwind CSS v4.

## Dev Commands

```bash
make dev                    # Start PostgreSQL (if not running) + backend (:8000) + frontend (:5173)
make stop                   # Kill uvicorn + vite processes
make test                   # uv run pytest (backend) + npm test (frontend)
make lint                   # Ruff lint + mypy + ESLint + prettier check
make build                  # Frontend production build
make format                 # Auto-format both frontend and backend
make docker-build           # Build Docker images (multi-stage)
make docker-up              # docker compose up -d
make docker-down            # docker compose down
make security               # Bandit + safety dependency scan
make db-backup              # pg_dump backup

cd backend && uv run pytest tests/ -v        # Backend tests only
cd frontend && npm run dev                   # Frontend only
cd frontend && npx tsc --noEmit              # TypeScript type-check
cd backend && uv run ruff check app/         # Python lint only
make install                # uv sync + npm install
```

Backend auto-reloads via `uvicorn --reload`. API docs at `http://localhost:8000/docs`.

## Database

**PostgreSQL** `postgresql://innovos:innovos_secret@localhost:5432/innovos`. Configured in `backend/.env` via `DATABASE_URL`.

PostgreSQL only (SQLite phased out). `knowledge_vectors.embedding` is `vector(4096)` via pgvector.

**Schema caveats:**

- PG lowercase-izes unquoted SQL aliases: `AS activeCount` → `activecount` in results. Always use lowercase aliases.
- `models` table uses composite PK `(provider_id, model_id)` — no auto-increment `id`.
- Timestamps stored as TEXT (`YYYY-MM-DD HH24:MI:SS`) for backward compat; prefer `TIMESTAMPTZ` in new columns.

## Project Structure

```
backend/
  app/
    api/          # FastAPI routes (auth, knowledge, admin, sidebar, workflow, etc.)
    algorithm/    # AI core: model_runtime, embedder, reranker, retriever, pipeline, crypto, key_manager
    services/     # Business logic: knowledge_base_service, knowledge_item_service, job system, orchestration
    tables/       # DB schema definitions (pg_schema.py — PostgreSQL only)
    main.py       # App entrypoint — logging config, router registration, startup hooks
frontend/
  src/
    features/     # Feature-based pages (knowledge, admin, dashboard, workflow, auth, etc.)
    components/   # Shared UI components (layout, common, rich-editor, etc.)
    store/        # Zustand 5 stores (useKnowledgeStore, useAuthStore, etc.)
    api/          # API client functions (auto JWT injection)
    types/        # TypeScript type definitions
    routes/       # React Router v7 routing (lazy-loaded pages)
```

## Key Architecture

- **Knowledge Base pipeline**: Upload → `KnowledgePipeline` (read + chunk + embed via Embedder) → `VectorStore` write via pgvector. Orchestrated by async job system (`KnowledgeJobManager`). Supports async file processing with retry and exponential backoff.
- **Job system**: 5 job types in `backend/app/services/knowledge_jobs/` — `prepare-root`, `index-documents`, `check-file-processing-result`, `delete-subtree`, `reindex-subtree`. Enqueued with idempotency keys, retry 3x with exponential backoff. Error callbacks on all async tasks.
- **Model registry**: `backend/app/algorithm/model_registry.py` loads 2600+ model entries lazily on first access. Capabilities (embedding, rerank, chat) determined by registry lookup → regex inference fallback.
- **Model config resolution**: 3-tier fallback — knowledge-base-level → global system settings → first available provider.
- **API Key management**: Provider-based architecture (inspired by CherryStudio). Keys encrypted with AES-256 Fernet + PBKDF2 (600K iterations, random salt). Pooled with per-provider round-robin + rate limiting.
- **Auth**: JWT tokens (24h expiry), bcrypt password hashing. Production requires `INNOVOS_JWT_SECRET` env var. Password minimum 8 characters.
- **Admin seeding**: Idempotent — `seed_if_empty()` creates admin only if none exists. Credentials from `INNOVOS_ADMIN_USER`/`INNOVOS_ADMIN_PASSWORD` env vars (default: auto-generated random password logged at startup).

## Security Features

- Security headers: CSP, HSTS, XFO, XSS-Protection, Referrer-Policy, Permissions-Policy
- Rate limiting: per-IP sliding window (login 10/min, register 3/min, API 60/min)
- Request ID tracking (X-Request-ID header)
- Structured JSON logging in production (ENV=production)
- Global exception handler with request ID
- Parameterized SQL queries only (no f-string SQL injection — all dynamic columns whitelisted)
- Connection pool hygiene: `with db_session() as db:` context manager guaranteed close
- CORS: Dev allows localhost:5173-5175. Production uses nginx same-origin.

## Known Gotchas

- **OpenAI SDK v2** no longer auto-appends `/v1` to `base_url`. Always call `ModelRuntime.ensure_v1_url(api_host)` before passing to `OpenAI()`.
- **Rerank API path**: Use `/v1/rerank`, not `/rerank`. SiliconFlow and most providers require the `/v1/` prefix.
- **Polling jitter**: `fetchItems()` toggles `loading` state by default. Pass `skipLoading=true` for background polls.
- **CORS**: Dev mode allows `localhost:5173-5175`. Production uses nginx same-origin, no CORS needed.
- **Docker**: Multi-stage builds, non-root user, HEALTHCHECK, resource limits, json-file logging with rotation.
- **Nginx**: gzip compression, 1y immutable cache for static assets, no-cache for index.html, security headers.
- **AI API timeout**: All OpenAI calls have `http_client=httpx.Client(timeout=Timeout(30.0, connect=10.0))`.
- **cherry-studio reference**: For implementation patterns, look at `/home/chou/cherry-studio/` — especially the knowledge service, model runtime, and job system.

## Style

- Backend: `snake_case` for Python, `camelCase` for API JSON fields (field mapping in services).
- Frontend: Tailwind utility classes only. Lucide React for icons (not Font Awesome). No component libraries (antd, styled-components).
- All user-visible text in Chinese. Error messages in Chinese.
- DB calls: always use `with db_session() as db:` or `get_db()` with `try/finally` for guaranteed connection return.

## Crypto & Key Management

Encryption keys (`INNOVOS_ENCRYPT_KEY`) must be **persistent and stable** — never rely on auto-generated keys that change on restart:

1. **Never delete or comment out** `INNOVOS_ENCRYPT_KEY` from `.env` — doing so will cause all encrypted API keys in the database to become permanently undecryptable.
2. **No silent fallbacks** — If the env var is unset, the code auto-generates a temp key and logs a warning. This is only for first-time dev setup, not a recovery path. The temp key is lost on restart.
3. **Key rotation** — If `INNOVOS_ENCRYPT_KEY` must change, existing encrypted keys will fail to decrypt. There is no "plaintext fallback". Plan accordingly: re-encrypt all stored keys with the new key.
4. **Format** — New encryption format uses version prefix `$` + random salt (16 bytes) + Fernet token, all base64-encoded. Legacy format (`gAAAAA...` prefix, fixed salt) is supported for backward compatibility only.
5. **`INNOVOS_JWT_SECRET`** is required in production; dev auto-generates a temp key (but it differs per worker in multi-worker mode — use sticky sessions or set the env var).

## Code Cleanup

**每次修改代码时必须同步清理冗余/过时代码。**

1. **删除而非注释** — 不需要的代码直接删除，不保留注释掉的代码块。
2. **检查引用** — 删除文件前全局搜索是否还有 import/引用，一并清理。
3. **函数/组件无引用则删** — `rg` 搜索确认无调用方后直接删除。
4. **API 端点废弃则删** — 后端路由 + 前端 API 函数 + 类型定义一起清理。
5. **依赖清理** — 不再使用的 pip/npm 包从 `pyproject.toml`/`package.json` 移出。
6. **文档同步** — 代码变更后同步更新 `AGENTS.md` 和相关 docs/ 文件。

示例：删除 `crypto.py` 时，同步清理了 `key_manager.py`、`model_service.py`、`model_runtime.py`、`ai_client.py`、`file_parser.py`、`conftest.py` 中所有 import 和调用引用，共删除 3 个文件 333 行。
