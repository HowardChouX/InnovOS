# InnovOS

**Stack:** Python FastAPI (backend) + React/Vite/TypeScript (frontend) + PostgreSQL + Tailwind CSS.

## Dev Commands

```bash
make dev                    # Start PostgreSQL (if not running) + backend (:8000) + frontend (:5173)
make stop                   # Kill uvicorn + vite processes
make test                   # uv run pytest (backend) + npm test (frontend)
cd backend && uv run pytest tests/ -v    # Backend tests only
cd frontend && npm run dev               # Frontend only
cd frontend && npx tsc --noEmit          # TypeScript type-check
make install                # uv sync + npm install
```

Backend auto-reloads via `uvicorn --reload`. API docs at `http://localhost:8000/docs`.

## Database

**PostgreSQL** `postgresql://innovos:innovos_secret@localhost:5432/innovos`. Configured in `backend/.env` via `DATABASE_URL`.

SQLite was dropped — `InnovOS_ACCOUNTS.db` was migrated and renamed to `.migrated`.

**Schema caveats:**
- PG lowercase-izes unquoted SQL aliases: `AS activeCount` → `activecount` in results. Always use lowercase aliases.
- `knowledge_vectors.embedding` is `vector(4096)` (pgvector). DROP TABLE on old schema then recreate with `CREATE TABLE IF NOT EXISTS`.
- `models` table uses composite PK `(provider_id, model_id)` — no auto-increment `id`.

## Project Structure

```
backend/
  app/
    api/          # FastAPI routes (auth, knowledge, admin, sidebar, etc.)
    algorithm/    # AI core: model_runtime, embedder, reranker, retriever, pipeline
    services/     # Business logic: knowledge CRUD, job system, orchestration
    tables/       # DB schema definitions (pg_schema.py for PG, sqlite_schema.py fallback)
    main.py       # App entrypoint — logging config, router registration, startup hooks
frontend/
  src/
    features/     # Feature-based pages (knowledge, admin, dashboard, modeling)
    store/        # Zustand stores (useKnowledgeStore)
    api/          # API client functions
    types/        # TypeScript type definitions
```

## Key Architecture

- **Knowledge Base pipeline**: Upload → `KnowledgePipeline` (read + chunk + embed via Embedder) → `VectorStore` write (SQLite BLOB / PG pgvector). Orchestrated by async job system (`KnowledgeJobManager`).
- **Job system**: 5 job types in `backend/app/services/knowledge_jobs/` — `prepare-root`, `index-documents`, `check-file-processing-result`, `delete-subtree`, `reindex-subtree`. Enqueued with idempotency keys, retry 3x with exponential backoff.
- **Model registry**: `backend/app/algorithm/model_registry.py` loads 2600+ model entries at startup. Capabilities (embedding, rerank, chat) determined by registry lookup → regex inference fallback.
- **Model config resolution**: 3-tier fallback — knowledge-base-level → global system settings → first available provider.

## Known Gotchas

- **OpenAI SDK v2** no longer auto-appends `/v1` to `base_url`. Always call `ModelRuntime.ensure_v1_url(api_host)` before passing to `OpenAI()`.
- **Rerank API path**: Use `/v1/rerank`, not `/rerank`. SiliconFlow and most providers require the `/v1/` prefix.
- **Polling jitter**: `fetchItems()` toggles `loading` state by default. Pass `skipLoading=true` for background polls.
- **CORS**: Dev mode allows `localhost:5173-5175`. Production uses nginx same-origin, no CORS needed.
- **Password reset**: `backend/app/seed.py` resets admin to `InnovOS2026@admin / admin123` on startup if no admin exists.
- **cherry-studio reference**: For implementation patterns, look at `/home/chou/cherry-studio/` — especially the knowledge service, model runtime, and job system.

## Style

- Backend: `snake_case` for Python, `camelCase` for API JSON fields (field mapping in services).
- Frontend: Tailwind utility classes only. Font Awesome 6 for icons. No component libraries (antd, styled-components).
- All user-visible text in Chinese. Error messages in Chinese.
