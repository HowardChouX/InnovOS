# PostgreSQL Development Startup — Design

**Date:** 2026-07-31
**Status:** Approved (brainstorming complete)
**Author:** Claude (brainstorming skill)

## Problem

`make dev` fails on this developer's machine with:

```
pg_ctl: could not start server
FATAL: could not create lock file "/run/postgresql/.s.PGSQL.5432.lock": No such file or directory
```

Root cause (systematic-debugging Phase 1): PostgreSQL 18.4 is installed locally;
its default Unix socket directory is `/run/postgresql/`, which does not exist on
this machine. The Makefile command `sudo -u postgres pg_ctl -D /var/lib/postgres/data start`
does not arrange for that directory, so the server cannot start.

A secondary problem: `make stop` only kills uvicorn and vite, never the Postgres
process — leaving it orphaned across dev sessions.

## Goal

Make `make dev` / `make stop` a complete, idempotent, one-command dev lifecycle
for the local Postgres cluster (no Docker, no systemd — keep the existing
`sudo pg_ctl` approach).

Non-goals:

- Switching to Docker Compose for PG (out of scope; existing docker-compose
  remains as alternate deployment).
- Switching to systemd unit for PG.
- Installing PostgreSQL or adjusting sudo NOPASSWD configuration.
- Migrating data, changing schemas, or changing backend connection pool logic.

## Approach (Option A from brainstorming)

Direct PG to use a writable socket directory under `/tmp` via the `-o "-k DIR"`
flag, and have the backend connect using `host=/tmp`. Keep the existing local
cluster at `/var/lib/postgres/data` and existing `postgres` system user.

### Rationale

- `/tmp` is always present, writable, and ephemeral — perfect for socket files.
- `host=/tmp` is the canonical psycopg2 way to connect via Unix socket while
  keeping the URL `localhost`-prefixed for tooling that expects a host.
- No new system dependencies, no new directories under `/run`, no new sudo
  surface area.

## Design

### 4.1 Lifecycle Flow

```
make dev
  └─ make start-db
      ├─ # /tmp is sticky-world-writable — already exists; nothing to create
      ├─ pg_isready -h $(PG_SOCKET_DIR) -p 5432 -q                       # idempotent
      │   └─ exits 0 → already running, skip
      └─ exits non-zero → sudo -u postgres pg_ctl \
              -D $(PG_DATA_DIR) \
              -o "-k $(PG_SOCKET_DIR)" \
              -l $(PG_LOG) \
              start
  └─ # poll up to 10s for ready
      until pg_isready -h $(PG_SOCKET_DIR) -p 5432 -q; do sleep 0.5; done
  └─ cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
  └─ sleep 2
  └─ cd frontend && npm run dev

make stop
  ├─ pkill -f "uvicorn app.main" 2>/dev/null; true
  ├─ pkill -f "vite" 2>/dev/null; true
  └─ sudo -u postgres pg_ctl \
        -D $(PG_DATA_DIR) \
        -o "-k $(PG_SOCKET_DIR)" \
        -m fast \
        stop 2>/dev/null; true
```

### 4.2 Makefile Variables

Add at the top of the Makefile (after `.PHONY`):

```make
# PostgreSQL (local cluster, sudo pg_ctl)
PG_DATA_DIR    ?= /var/lib/postgres/data
PG_SOCKET_DIR  ?= /tmp
PG_LOG         ?= /tmp/pg.log
PG_PORT        ?= 5432
```

The `?=` makes them overridable from the environment (e.g.
`make dev PG_SOCKET_DIR=/home/chou/.pgsock`).

### 4.3 `.env` Change

Append (do not duplicate) a single line to `/home/chou/InnovOS/.env`:

```
DATABASE_URL=postgresql://innovos:ec8d35455f84fd5c749d@localhost:5432/innovos?host=/tmp
```

- Existing `POSTGRES_PASSWORD=ec8d35455f84fd5c749d` is reused.
- `innovos` user / `innovos` database name is kept (matches the local cluster
  convention that the backend already uses; verified by inspecting `database.py`
  defaults).
- `host=/tmp` tells psycopg2 to use the Unix socket we just created.

Note: The local cluster's `pg_hba.conf` already permits `local` connections (read
during investigation). The `host=/tmp` URL opens a Unix-domain socket, which
matches the `local` auth record — no `pg_hba.conf` change required.

### 4.4 Error Handling

- `start-db` polls `pg_isready` for up to 10s. If it does not become ready:
  - print the last 20 lines of `$(PG_LOG)`
  - exit 1 with a clear error message
- `start-db` does not background the PG process; `pg_ctl start` daemonizes and
  returns immediately, so the parent shell is unaffected.
- `make stop` swallows failures from `pg_ctl stop` (PG may already be down) with
  `|| true` so the target never fails.
- `start-db` does not need to create `$(PG_SOCKET_DIR)` when it is `/tmp`
  (already present). If callers override `PG_SOCKET_DIR` to a non-existent
  path, `pg_ctl` will still fail and the user must `mkdir -p` it themselves;
  this is documented.

### 4.5 Idempotency

- `pg_isready` check at the top of `start-db` skips startup if PG is already
  running.
- `make stop` is safe to run when PG is not running.
- Re-running `make dev` after `make stop` will start PG again on the next
  invocation.

### 4.6 Why `-m fast` (not `immediate`)

`fast` cancels active queries and rolls back, then runs a clean shutdown.
`immediate` aborts without checkpoint and risks data corruption. For an
independent dev environment, `fast` is the right balance.

## Files Changed

| File                                           | Change                                                     |
| ---------------------------------------------- | ---------------------------------------------------------- |
| `Makefile`                                     | Add PG variables; rewrite `start-db`; extend `stop`        |
| `.env`                                         | Add `DATABASE_URL` line with `host=/tmp`                   |
| `README.md`                                    | Document dev PG socket path and `make dev`/`make stop`     |
| `CLAUDE.md`                                    | Note PG socket path in dev workflow section                |
| `docs/superpowers/specs/2026-07-31-...md`      | This spec                                                  |

## Acceptance Criteria

After implementation, all of the following must pass:

1. `make dev` boots and the `start-db` command exits 0 within 10s.
2. `pg_isready -h /tmp -p 5432` reports `accepting connections`.
3. `curl -s http://localhost:8000/api/health` returns 200.
4. `curl -s http://localhost:5173` returns 200.
5. `make stop` exits 0 and `pg_isready -h /tmp -p 5432` reports
   `no response` within 5s.
6. No `uvicorn` or `vite` processes remain after `make stop`.
7. Re-running `make dev` after `make stop` brings everything back up.
8. `make dev` is idempotent — running it twice in a row does not error on the
   second invocation.

## Verification Command

The implementer (or a reviewer) will run `superpowers:verification-before-completion`
before claiming done. The verification will execute the acceptance commands
above and paste the output as evidence.

## Risks

- **Sudo NOPASSWD still required.** This design does not change the
  `sudo -u postgres` requirement. If the user lacks it, the design still fails.
  This is a known precondition documented in the README, not a bug.
- **`/tmp` is shared.** Any user on the box can read/write the socket dir if
  permissions allow. PG respected default Unix-socket permissions (`0750`,
  owner `postgres`). Acceptable for a dev box; not appropriate for shared
  production.
- **Existing local cluster permissions.** `/var/lib/postgres/data` is owned by
  `postgres:postgres` with mode `0700` — unchanged by this design. `pg_ctl`
  command path is unchanged.

## Rollback

Single `git revert` of the four files restores the previous behavior. No
database migration happens — the cluster directory is untouched.

## Out of Scope (Explicit YAGNI)

- Auto-creating `backend/.env` or copying `.env.example`.
- `make db-status` or other diagnostic targets.
- Multi-socket-dir support beyond the `PG_SOCKET_DIR` variable.
- Healthcheck of backend / frontend in the Makefile (those have their own
  health endpoints).
- Documenting or modifying the `docker-compose.yml` Postgres service.
- Adding a signoff that warns if `sudo -u postgres` would prompt for a password.
