# PostgreSQL Development Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `make dev` and `make stop` a complete, idempotent dev lifecycle for the local PostgreSQL 18.4 cluster on this developer's machine, by redirecting the Unix socket to `/tmp` and connecting the backend through `host=/tmp`.

**Architecture:** Add `PG_*` variables to the Makefile; rewrite `start-db` to use `pg_ctl -o "-k /tmp"` and a `pg_isready` polling loop; extend `stop` to `pg_ctl -m fast stop`. Append a single `DATABASE_URL` line to `.env` so psycopg2 connects via the new socket. Document the change in `README.md` and `CLAUDE.md`.

**Tech Stack:** GNU Make 4.x, PostgreSQL 18.4 (`pg_ctl`, `pg_isready`), `sudo` (NOPASSWD for `postgres`), psycopg2 (Unix socket via `host=/tmp`).

## Global Constraints

- Local cluster at `/var/lib/postgres/data` (system user `postgres`, mode `0700`). Untouched.
- Socket directory is `PG_SOCKET_DIR ?= /tmp` (overridable via env).
- `start-db` MUST be idempotent — running it twice in a row MUST NOT error.
- `pg_ctl stop` failure (PG already down) MUST NOT fail `make stop`.
- `local all all trust` is in `pg_hba.conf` — Unix-socket auth needs no password, so the `innovos` user / `innovos` database may not need to exist in the local cluster; existing backend defaults will be used.
- Commit style: `<type>(<scope>): <description>` (feat, fix, refactor, docs, chore).
- All steps use `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` in commit body.

---

## File Structure

| File      | Responsibility                                                                  |
| --------- | ------------------------------------------------------------------------------- |
| `Makefile`            | Expose `PG_*` variables; rewrite `start-db`; extend `stop`. |
| `.env`                | Add `DATABASE_URL` with `host=/tmp`. |
| `README.md`           | Document dev PG socket path + `make dev`/`make stop` semantics. |
| `CLAUDE.md`           | One-line note in "Build & Development" section. |

No new files outside these four. No tests added (`make dev`/`make stop` is shell orchestration; the operational acceptance commands in the spec serve as the test plan).

---

## Task 1: Add PG variables and rewrite `start-db` / `stop`

**Files:**
- Modify: `Makefile` (top after `.PHONY`, plus `start-db`, plus `stop`)

**Interfaces:**
- Produces: Make variables `PG_DATA_DIR`, `PG_SOCKET_DIR`, `PG_LOG`, `PG_PORT` (all overridable via `?=`).
- Produces: `make start-db` target that:
  - Polls `pg_isready -h $(PG_SOCKET_DIR) -p $(PG_PORT) -q`; if it exits 0, exits 0 immediately.
  - Otherwise `sudo -u postgres pg_ctl -D $(PG_DATA_DIR) -o "-k $(PG_SOCKET_DIR)" -l $(PG_LOG) start`.
  - Polls up to 10s for `pg_isready`; on timeout, `tail -20 $(PG_LOG)` and exit 1.
- Produces: `make stop` extended with `sudo -u postgres pg_ctl -D $(PG_DATA_DIR) -o "-k $(PG_SOCKET_DIR)" -m fast stop 2>/dev/null; true`.

**Note before starting:** Read the current `Makefile` (`/home/chou/InnovOS/Makefile`) for exact line context. The relevant lines are `.PHONY` (line 1), `start-db` (lines 15-16), `stop` (lines 18-22). Do not change other targets.

- [ ] **Step 1: Add the PG variables block right after the `.PHONY` line**

Insert immediately after `.PHONY: dev stop test lint quality format clean install build security docker-up docker-down db-backup setup-hooks` (which is line 1) and before the comment block that begins `# ══════════════════════════════════════════════` (line 3). The content to insert:

```make

# PostgreSQL local cluster (sudo pg_ctl) — overridable from env
PG_DATA_DIR    ?= /var/lib/postgres/data
PG_SOCKET_DIR  ?= /tmp
PG_LOG         ?= /tmp/pg.log
PG_PORT        ?= 5432
```

The block must end with a blank line so the existing comment block continues to render correctly.

- [ ] **Step 2: Rewrite `start-db`**

Replace the entire `start-db` target (lines 15-16) with:

```make
start-db:
	@pg_isready -h $(PG_SOCKET_DIR) -p $(PG_PORT) -q 2>/dev/null && { echo "=== PostgreSQL already running on $(PG_SOCKET_DIR):$(PG_PORT) ==="; exit 0; } || true
	@echo "=== Starting PostgreSQL (socket: $(PG_SOCKET_DIR)) ==="
	@sudo -u postgres pg_ctl -D $(PG_DATA_DIR) -o "-k $(PG_SOCKET_DIR)" -l $(PG_LOG) start
	@echo "=== Waiting for PostgreSQL to accept connections ==="
	@for i in $$(seq 1 20); do \
		pg_isready -h $(PG_SOCKET_DIR) -p $(PG_PORT) -q && { echo "=== PostgreSQL ready ==="; exit 0; }; \
		sleep 0.5; \
	done; \
	echo "ERROR: PostgreSQL did not become ready in 10s. Last 20 lines of $(PG_LOG):" >&2; \
	sudo -u postgres tail -20 $(PG_LOG) >&2; \
	exit 1
```

This satisfies all of:
- Idempotent (`pg_isready` exits 0 → skip).
- `-o "-k $(PG_SOCKET_DIR)"` redirects socket creation.
- 10s polling loop (20 × 0.5s) instead of arbitrary `sleep 2`.
- On failure, dumps tail of `$(PG_LOG)` and exits 1.

- [ ] **Step 3: Extend `stop` to also stop PG**

Replace the `stop` target (lines 18-22) with:

```make
stop:
	@echo "=== Stopping frontend / backend ==="
	@pkill -f "uvicorn app.main" 2>/dev/null; true
	@pkill -f "vite" 2>/dev/null; true
	@echo "=== Stopping PostgreSQL ==="
	@sudo -u postgres pg_ctl -D $(PG_DATA_DIR) -o "-k $(PG_SOCKET_DIR)" -m fast stop 2>/dev/null; true
	@echo "Stopped."
```

The `2>/dev/null; true` ensures the target never fails when PG is already down.

- [ ] **Step 4: Verify the Makefile parses**

Run: `make -n start-db` (dry-run — prints commands without executing them).
Expected: commands including `pg_isready`, `pg_ctl -D /var/lib/postgres/data -o "-k /tmp" -l /tmp/pg.log start`, and the polling loop. No syntax errors.

Run: `make -n stop`.
Expected: pkill commands then `pg_ctl ... -m fast stop`. No syntax errors.

Run: `make start-db PG_SOCKET_DIR=/tmp/pg_test` (override variable).
Expected: command output references `/tmp/pg_test` instead of `/tmp`. Confirms `?=` works.

- [ ] **Step 5: Commit**

```bash
git add Makefile
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "feat(make): start/stop local Postgres via /tmp socket

PG_DATA_DIR/PG_SOCKET_DIR/PG_LOG/PG_PORT now overridable.
start-db polls pg_isready for 10s and dumps tail of pg.log on failure.
stop also issues pg_ctl -m fast stop.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Add `DATABASE_URL` to `.env`

**Files:**
- Modify: `/home/chou/InnovOS/.env` (append one line)

**Interfaces:**
- Produces: `DATABASE_URL` env var with `host=/tmp` query parameter so psycopg2 uses the Unix socket we just configured.

**Why this DATABASE_URL exactly:**
- `postgresql+psycopg2://` is the SQLAlchemy URL scheme (matches `backend/app/database.py`).
- User `innovos` / db `innovos` are the names the backend and docker-compose already use.
- Password `ec8d35455f84fd5c749d` is `POSTGRES_PASSWORD` already in `.env` — read it via grep to keep in sync.
- `host=/tmp` is the SQLAlchemy/psycopg2 way to specify a Unix socket directory.

- [ ] **Step 1: Read the existing `POSTGRES_PASSWORD` value**

Run: `grep '^POSTGRES_PASSWORD=' /home/chou/InnovOS/.env`
Expected: a single line like `POSTGRES_PASSWORD=<hex>`. Use that exact value in the next step.

- [ ] **Step 2: Append `DATABASE_URL` to `.env`**

Read the current `.env` first, then append the following line at the end (after the last existing line; ensure a trailing newline):

```
DATABASE_URL=postgresql+psycopg2://innovos:<POSTGRES_PASSWORD_VALUE>@localhost:5432/innovos?host=/tmp
```

Replace `<POSTGRES_PASSWORD_VALUE>` with the actual value from Step 1 (do NOT hardcode the literal hex from this plan — it could be different later).

Do not duplicate the line. Use Edit to find the last existing line and append, or use `tail -1` to confirm where the file ends.

- [ ] **Step 3: Verify the line is appended exactly once**

Run: `grep -c '^DATABASE_URL=' /home/chou/InnovOS/.env`
Expected: `1`

Run: `grep '^DATABASE_URL=' /home/chou/InnovOS/.env`
Expected: a single line containing `host=/tmp`.

- [ ] **Step 4: Commit**

```bash
git add .env
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "feat(env): set DATABASE_URL with host=/tmp for backend unix-socket connect

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Document `make dev` / `make stop` in `README.md`

**Files:**
- Modify: `/home/chou/InnovOS/README.md`

- [ ] **Step 1: Find the "Development" or "Quick Start" section**

Run: `grep -n -E '^#|^##' /home/chou/InnovOS/README.md`
Expected: a list of headings. Identify the section that mentions `make dev` or "quick start". Note the heading line number.

- [ ] **Step 2: Add a "PostgreSQL socket path" subsection**

After the existing `make dev` paragraph (do not delete it), insert:

```markdown
### PostgreSQL socket path

`make dev` starts the local PostgreSQL cluster via `sudo pg_ctl`. The default
Unix socket directory is redirected to `/tmp` (via `pg_ctl -o "-k /tmp"`)
because `/run/postgresql` is not present on this machine. The backend
connects through `DATABASE_URL=...@localhost:5432/innovos?host=/tmp` so
psycopg2 uses the same socket.

To use a different socket directory, override `PG_SOCKET_DIR`:

```bash
make dev PG_SOCKET_DIR=/home/you/.pgsock
```

You will need to create the directory yourself first.
```

- [ ] **Step 3: Render the README to confirm**

Run: `grep -A 2 'PostgreSQL socket path' /home/chou/InnovOS/README.md`
Expected: the new heading appears exactly once.

- [ ] **Step 4: Commit**

```bash
git add README.md
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "docs(readme): document PostgreSQL socket path for make dev/stop

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Add one-line note to `CLAUDE.md`

**Files:**
- Modify: `/home/chou/InnovOS/CLAUDE.md`

- [ ] **Step 1: Find the "Build & Development Commands" section**

Run: `grep -n 'Build & Development' /home/chou/InnovOS/CLAUDE.md`
Expected: a line number. The section already documents `make dev`.

- [ ] **Step 2: Add a one-line note**

Right after the existing `make dev` line in the "Build & Development Commands" block, insert:

```markdown
# PG socket: /tmp (override with PG_SOCKET_DIR=...). PG stopped by `make stop`.
```

- [ ] **Step 3: Verify**

Run: `grep -n 'PG socket' /home/chou/InnovOS/CLAUDE.md`
Expected: exactly one match.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "docs(claude): note PG socket path in dev commands

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: End-to-end verification (operational acceptance)

**Files:** None — read-only verification.

**Acceptance commands** (these are the spec's 8 acceptance criteria, made concrete):

- [ ] **Step 1: Stop anything currently running**

```bash
make stop 2>&1
sudo -u postgres pg_isready -h /tmp -p 5432 2>&1 || true
pgrep -af 'uvicorn|vite' 2>&1 || echo "no app processes"
```

Expected: `make stop` exits 0; `pg_isready` reports `no response` (or PostgreSQL is not accepting connections); no `uvicorn`/`vite` processes.

- [ ] **Step 2: Start dev in background and wait**

```bash
make dev > /tmp/dev.log 2>&1 &
DEVPID=$!
echo "started dev PID=$DEVPID"
for i in $(seq 1 60); do
  pg_isready -h /tmp -p 5432 -q && curl -sf http://localhost:8000/api/health && curl -sf -o /dev/null http://localhost:5173 && break
  sleep 1
done
```

Expected: the loop completes within ~30s; `pg_isready` reports `accepting connections`; backend and frontend reachable.

If it does not complete, `tail -50 /tmp/dev.log` and `sudo -u postgres tail -40 /tmp/pg.log` to diagnose.

- [ ] **Step 3: Confirm running processes**

```bash
pgrep -af 'uvicorn|vite|postgres' | head -20
sudo -u postgres pg_isready -h /tmp -p 5432
```

Expected: uvicorn, vite, and a postgres process are listed; `pg_isready` shows `accepting connections`.

- [ ] **Step 4: Run `make stop`**

```bash
make stop 2>&1
sleep 3
pgrep -af 'uvicorn|vite' 2>&1 || echo "no app processes"
sudo -u postgres pg_isready -h /tmp -p 5432 2>&1 || true
```

Expected: `make stop` exits 0; no `uvicorn`/`vite` processes; `pg_isready` reports `no response`.

- [ ] **Step 5: Idempotency check — restart**

```bash
make dev > /tmp/dev2.log 2>&1 &
DEVPID2=$!
for i in $(seq 1 60); do
  pg_isready -h /tmp -p 5432 -q && break
  sleep 1
done
sudo -u postgres pg_isready -h /tmp -p 5432
make stop 2>&1
```

Expected: cluster starts cleanly on second invocation; `pg_isready` accepts; `make stop` succeeds.

- [ ] **Step 6: Run `make dev` twice in a row to verify idempotency of `start-db`**

```bash
make start-db > /tmp/sdb1.log 2>&1 && echo "PASS: start-db #1"
make start-db > /tmp/sdb2.log 2>&1 && echo "PASS: start-db #2"
sudo -u postgres pg_isready -h /tmp -p 5432
make stop 2>&1 | tail -5
```

Expected: both `start-db` invocations exit 0; `start-db` #2 prints "already running" (or returns 0 quickly); `make stop` succeeds.

- [ ] **Step 7: Summarize results**

If all 6 steps pass, post a one-line summary in the response:

```
8/8 acceptance criteria pass: start-db idempotent, stop clean, both bring back up.
```

If anything fails, **DO NOT claim done**. Instead:
1. Read `/tmp/pg.log` and `/tmp/dev.log`.
2. Form a single hypothesis (per `superpowers:systematic-debugging`).
3. Iterate Task 1-2 if the failure is in the Makefile or `.env`.
4. Re-run this verification.

---

## Self-Review (run before declaring the plan complete)

- [ ] **Spec coverage:** every section in `docs/superpowers/specs/2026-07-31-postgres-dev-startup-design.md` is covered:
  - §4.1 Lifecycle Flow → Task 1 (`start-db` poll, `stop` pg_ctl).
  - §4.2 Makefile Variables → Task 1 Step 1.
  - §4.3 `.env` Change → Task 2.
  - §4.4 Error Handling → Task 1 Step 2 (timeout + tail-dump).
  - §4.5 Idempotency → Task 5 Step 6 (explicit idempotency check).
  - §4.6 Why `-m fast` → Task 1 Step 3 (`-m fast` chosen).
  - §Files Changed → all 4 files have a task.
  - §Acceptance Criteria (8 items) → Task 5 (operational verification).

- [ ] **No placeholders:** No TBD/TODO/"appropriate"/"handle edge cases" anywhere.

- [ ] **Type consistency:** Variable names (`PG_DATA_DIR`, `PG_SOCKET_DIR`, `PG_LOG`, `PG_PORT`) used everywhere identically. `start-db` and `stop` both use `-o "-k $(PG_SOCKET_DIR)"`. `host=/tmp` consistent in `.env` and README.

- [ ] **Scope:** Single implementation plan, no decomposition needed.

- [ ] **Commit style:** Each commit follows `<type>(<scope>): <description>` and ends with the required `Co-Authored-By` trailer.
