"""
Notification API tests — mock DB without PostgreSQL.

Covers all 10 notification endpoints:
  1. GET  /api/notifications              — list
  2. GET  /api/notifications/unread-count  — unread count
  3. PUT  /api/notifications/{id}/read     — mark one read
  4. PUT  /api/notifications/read-all      — mark all read
  5. DELETE /api/notifications/clear-all   — clear all
  6. DELETE /api/notifications/{id}        — delete single
  7. POST /api/notifications               — admin create
  8. POST /api/notifications/batch         — admin batch send
  9. GET  /api/notifications/sent          — admin sent list
  10. PUT /api/notifications/{id}/recall   — admin recall
"""

import re
import pytest
from fastapi.testclient import TestClient


class MockRow(dict):
    """Dict row that supports both string and integer indexing."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class MockDB:
    """In-memory mock database supporting multiple tables."""

    def __init__(self):
        self._tables: dict[str, dict[int, dict]] = {}
        self._next_ids: dict[str, int] = {}
        self._last_result: list[MockRow] = []

    # ── internal helpers ──────────────────────────────────────

    def _ensure(self, table: str) -> None:
        if table not in self._tables:
            self._tables[table] = {}
            self._next_ids[table] = 1

    def _table_name(self, sql: str) -> str:
        upper = sql.upper().strip()
        for kw in ("UPDATE ", "INTO ", "FROM "):
            idx = upper.find(kw)
            if idx >= 0:
                after = upper[idx + len(kw):].strip()
                tbl = after.split()[0].rstrip(";,()")
                return tbl.lower()
        return ""

    def _strip_suffix(self, text: str) -> str:
        for kw in ("ORDER BY", "LIMIT", "OFFSET", "RETURNING"):
            idx = text.upper().find(kw)
            if idx >= 0:
                text = text[:idx]
        return text.strip()

    @staticmethod
    def _strip_alias(col: str) -> str:
        """Strip table alias prefix (e.g. 's.task_id' → 'task_id')."""
        return col.split(".")[-1] if "." in col else col

    def _where_conditions(self, sql: str) -> list:
        """Parse WHERE clause into list of condition groups (OR-separated)."""
        if "WHERE" not in sql.upper():
            return []
        where_part = sql.split("WHERE", 1)[1].strip()
        where_part = self._strip_suffix(where_part)
        or_groups = re.split(r'\s+OR\s+', where_part, flags=re.IGNORECASE)
        result = []
        for group in or_groups:
            conditions = []
            clauses = re.split(r'\s+AND\s+', group.strip(), flags=re.IGNORECASE)
            for clause in clauses:
                clause = clause.strip()
                if not clause:
                    continue
                if " LIKE " in clause.upper():
                    col = self._strip_alias(clause.split()[0].strip().lower())
                    val_part = clause.upper().split(" LIKE ")[1].strip()
                    if val_part == "?":
                        conditions.append((col, "LIKE", True, None))
                    else:
                        conditions.append((col, "LIKE", False, val_part.strip("'\"")))
                elif " IN " in clause.upper():
                    col = self._strip_alias(clause.split()[0].strip().lower())
                    in_part = clause.upper().split(" IN ")[1]
                    num_q = in_part.count("?")
                    conditions.append((col, "IN", True, num_q))
                elif "=?" in clause or "= ?" in clause:
                    norm = clause.replace("= ?", "=?")
                    col = self._strip_alias(norm.split("=?")[0].strip().lower())
                    right = norm.split("=?")[1].strip() if "=?" in norm else ""
                    if right == "" or right == "?":
                        conditions.append((col, "=", True, None))
                    else:
                        try:
                            conditions.append((col, "=", False, int(right)))
                        except ValueError:
                            conditions.append((col, "=", False, right.strip("'\"")))
                elif "=" in clause:
                    col, val_str = clause.split("=", 1)
                    col = self._strip_alias(col.strip().lower())
                    val_str = val_str.strip()
                    if val_str.startswith("'"):
                        conditions.append((col, "=", False, val_str.strip("'")))
                    else:
                        try:
                            conditions.append((col, "=", False, int(val_str)))
                        except ValueError:
                            conditions.append((col, "=", False, val_str))
            if conditions:
                result.append(conditions)
        return result

    def _filter_rows(self, table: str, condition_groups: list,
                     params: list) -> tuple[list, int]:
        """Filter rows using OR-of-ANDs logic."""
        all_rows = list(self._tables.get(table, {}).values())
        # No conditions → return all rows
        if not condition_groups:
            return all_rows, 0
        pi = 0
        matched_ids = set()
        for group in condition_groups:
            group_rows = list(all_rows)
            for col, op, is_param, val in group:
                if op == "=":
                    actual = params[pi] if is_param else val
                    if is_param:
                        pi += 1
                    group_rows = [r for r in group_rows if r.get(col) == actual]
                elif op == "LIKE":
                    pattern = params[pi] if is_param else val
                    if is_param:
                        pi += 1
                    if isinstance(pattern, str) and pattern.startswith("%") and pattern.endswith("%"):
                        substr = pattern[1:-1].lower()
                        group_rows = [r for r in group_rows if substr in str(r.get(col, "")).lower()]
                    else:
                        group_rows = [r for r in group_rows if str(r.get(col, "")) == str(pattern)]
                elif op == "IN":
                    count = val
                    in_vals = params[pi:pi + count]
                    pi += count
                    group_rows = [r for r in group_rows if r.get(col) in in_vals]
            matched_ids.update(r["id"] for r in group_rows)
        return [r for r in all_rows if r["id"] in matched_ids], pi

    def _order_by(self, sql: str) -> tuple[str | None, bool]:
        if "ORDER BY" not in sql.upper():
            return None, False
        order_part = sql.upper().split("ORDER BY")[1].strip()
        for kw in ("LIMIT", "OFFSET", "RETURNING"):
            idx = order_part.upper().find(kw)
            if idx >= 0:
                order_part = order_part[:idx]
        parts = order_part.split()
        return parts[0].lower().rstrip(","), len(parts) > 1 and parts[1].upper() == "DESC"

    def _limit_offset(self, sql: str, remaining: list) -> tuple:
        limit, offset, pi = None, 0, 0
        if "LIMIT" in sql.upper():
            part = sql.upper().split("LIMIT")[1].strip().split()[0]
            if part == "?" and pi < len(remaining):
                limit = remaining[pi]; pi += 1
            else:
                limit = int(part)
        if "OFFSET" in sql.upper():
            part = sql.upper().split("OFFSET")[1].strip().split()[0]
            if part == "?" and pi < len(remaining):
                offset = remaining[pi]; pi += 1
            else:
                offset = int(part)
        return limit, offset

    def _select_cols(self, sql: str) -> list[str]:
        select_part = sql.split("FROM")[0].replace("SELECT", "", 1).strip()
        cols = []
        for c in select_part.split(","):
            c = c.strip()
            if "." in c:
                c = c.split(".")[1]
            cols.append(c.lower().rstrip(" as"))
        return cols

    def _insert_cols(self, sql: str) -> list[str]:
        m = re.search(r'\(([^)]+)\)\s*VALUES', sql, re.IGNORECASE)
        if m:
            return [c.strip().lower() for c in m.group(1).split(",")]
        return []

    def _set_cols(self, sql: str) -> list:
        set_part = sql.upper().split("SET")[1]
        where_idx = set_part.upper().find("WHERE")
        if where_idx >= 0:
            set_part = set_part[:where_idx]
        cols = []
        for assign in set_part.split(","):
            if "=?" in assign or "= ?" in assign:
                col = assign.replace("= ?", "=?").split("=?")[0].strip().lower()
                cols.append((col, True, None))
            elif "=" in assign:
                col, val_str = assign.split("=", 1)
                col = col.strip().lower()
                val_str = val_str.strip()
                if val_str.startswith("'"):
                    cols.append((col, False, val_str.strip("'")))
                else:
                    try:
                        cols.append((col, False, int(val_str)))
                    except ValueError:
                        cols.append((col, False, val_str))
        return cols

    # ── SQL dispatchers ───────────────────────────────────────

    def execute(self, sql: str, params=None):
        self._last_result = []
        params = list(params) if params else []
        upper = sql.upper().strip()

        # Handle bare "SELECT 1" (health check)
        if upper == "SELECT 1":
            self._last_result = [MockRow({"1": 1})]
            return self

        if upper.startswith("SELECT"):
            self._exec_select(sql, params)
        elif upper.startswith("INSERT"):
            self._exec_insert(sql, params)
        elif upper.startswith("UPDATE"):
            self._exec_update(sql, params)
        elif upper.startswith("DELETE"):
            self._exec_delete(sql, params)
        return self

    def _exec_select(self, sql: str, params: list) -> None:
        upper = sql.upper()

        # Handle JOIN queries
        if " JOIN " in upper:
            self._exec_join(sql, params)
            return

        table = self._table_name(sql)
        if not table:
            return
        self._ensure(table)

        conditions = self._where_conditions(sql)
        rows, pi = self._filter_rows(table, conditions, params)
        remaining = params[pi:]

        order_col, desc = self._order_by(sql)
        if order_col:
            rows.sort(key=lambda r: str(r.get(order_col, "") or ""), reverse=desc)

        if "COUNT(*)" in upper:
            self._last_result = [MockRow({"count(*)": len(rows)})]
            return

        limit, offset = self._limit_offset(sql, remaining)
        if offset or limit is not None:
            rows = rows[offset:(offset + limit) if limit else None]

        cols = self._select_cols(sql)
        if cols != ["*"]:
            self._last_result = [MockRow({c: r.get(c) for c in cols}) for r in rows]
        else:
            self._last_result = [MockRow(r.copy()) for r in rows]

    def _exec_join(self, sql: str, params: list) -> None:
        m = re.search(
            r'FROM\s+(\w+)\s+\w+\s+JOIN\s+(\w+)\s+\w+\s+ON\s+\w+\.(\w+)\s*=\s*\w+\.(\w+)',
            sql, re.IGNORECASE,
        )
        if not m:
            return
        t1, t2 = m.group(1).lower(), m.group(2).lower()
        t1_col, t2_col = m.group(3).lower(), m.group(4).lower()
        self._ensure(t1)
        self._ensure(t2)

        # Build joined rows first (all column pairs merged)
        all_joined = []
        for r1 in self._tables[t1].values():
            for r2 in self._tables[t2].values():
                if r1.get(t1_col) == r2.get(t2_col):
                    merged = r1.copy()
                    merged.update(r2)
                    all_joined.append(merged)
                    break

        if "COUNT(*)" in sql.upper():
            self._last_result = [MockRow({"count(*)": len(all_joined)})]
            return

        # Apply WHERE conditions (OR-of-ANDs) on the joined result
        conditions = self._where_conditions(sql)
        if conditions:
            pi = 0
            matched_ids = set()
            for group in conditions:
                filtered = list(all_joined)
                for col, op, is_param, val in group:
                    if op == "=":
                        actual = params[pi] if is_param else val
                        if is_param:
                            pi += 1
                        filtered = [r for r in filtered if r.get(col) == actual]
                    elif op == "LIKE":
                        pattern = params[pi] if is_param else val
                        if is_param:
                            pi += 1
                        if isinstance(pattern, str) and pattern.startswith("%") and pattern.endswith("%"):
                            substr = pattern[1:-1].lower()
                            filtered = [r for r in filtered if substr in str(r.get(col, "")).lower()]
                        else:
                            filtered = [r for r in filtered if str(r.get(col, "")) == str(pattern)]
                # Collect unique matched rows by index (avoid id() reuse issues)
                for r in filtered:
                    matched_ids.add(all_joined.index(r))
            joined = [all_joined[i] for i in sorted(matched_ids)]
        else:
            joined = all_joined

        cols = self._select_cols(sql)
        if cols != ["*"]:
            self._last_result = [MockRow({c: r.get(c) for c in cols}) for r in joined]
        else:
            self._last_result = [MockRow(r.copy()) for r in joined]

    def _exec_insert(self, sql: str, params: list) -> None:
        table = self._table_name(sql)
        self._ensure(table)
        cols = self._insert_cols(sql)
        nid = self._next_ids[table]
        self._next_ids[table] += 1
        row = {"id": nid}
        for i, col in enumerate(cols):
            if i < len(params):
                row[col] = params[i]
        self._tables[table][nid] = row

        if "RETURNING" in sql.upper():
            ret_part = sql.upper().split("RETURNING")[1].strip()
            ret_cols = [c.strip().lower() for c in ret_part.split(",")]
            self._last_result = [MockRow({c: row.get(c) for c in ret_cols})]

    def _exec_update(self, sql: str, params: list) -> None:
        table = self._table_name(sql)
        if not table:
            return
        self._ensure(table)
        set_cols = self._set_cols(sql)
        pi = 0
        set_vals = {}
        for col, is_param, val in set_cols:
            if is_param:
                set_vals[col] = params[pi]; pi += 1
            else:
                set_vals[col] = val
        conditions = self._where_conditions(sql)
        where_params = params[pi:]
        rows, _ = self._filter_rows(table, conditions, where_params)
        for row in rows:
            for col, val in set_vals.items():
                self._tables[table][row["id"]][col] = val

    def _exec_delete(self, sql: str, params: list) -> None:
        table = self._table_name(sql)
        if not table:
            return
        self._ensure(table)
        conditions = self._where_conditions(sql)
        to_delete, _ = self._filter_rows(table, conditions, params)
        for row in to_delete:
            del self._tables[table][row["id"]]

    def fetchone(self):
        return self._last_result[0] if self._last_result else None

    def fetchall(self):
        return self._last_result

    def commit(self):
        pass

    def close(self):
        pass

    def __iter__(self):
        return iter(self._last_result)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def client(mock_db, monkeypatch):
    """TestClient with notifications router and monkeypatched get_db."""
    monkeypatch.setattr("app.database.get_db", lambda: mock_db)
    monkeypatch.setattr("app.auth.get_db", lambda: mock_db)

    from app.api.notifications import router

    # Also patch the module-local reference (cached on first import)
    monkeypatch.setattr("app.api.notifications.get_db", lambda: mock_db)

    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


@pytest.fixture
def db_with_user(mock_db):
    """Seed a regular user (id=1) and an admin user (id=2) in mock DB."""
    mock_db._tables["users"] = {}
    mock_db._tables["users"][1] = {
        "id": 1, "username": "testuser", "password_hash": "x",
        "role": "user", "email": "", "is_active": 1,
        "created_at": "2024-01-01 00:00:00", "token_version": 0,
    }
    mock_db._tables["users"][2] = {
        "id": 2, "username": "admin", "password_hash": "x",
        "role": "admin", "email": "", "is_active": 1,
        "created_at": "2024-01-01 00:00:00", "token_version": 0,
    }
    mock_db._next_ids["users"] = 3
    return mock_db


def _user_token(user_id: int, role: str = "user") -> str:
    """Create a JWT for the given user."""
    from app.auth import create_access_token
    return create_access_token({"user_id": user_id, "role": role})


def _admin_token() -> str:
    """Create a JWT for the admin (env-based, user_id=0)."""
    from app.auth import create_access_token
    return create_access_token({"user_id": 0, "role": "admin", "username": "admin"})


# Need FastAPI here for the client fixture
from fastapi import FastAPI


# ══════════════════════════════════════════════════════════════
#  Tests
# ══════════════════════════════════════════════════════════════


class TestListNotifications:
    """GET /api/notifications — notification list"""

    def test_list_empty(self, client, db_with_user):
        resp = client.get("/api/notifications", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_list_with_notifications(self, client, db_with_user):
        """Returns notifications for the current user, ordered by created_at DESC."""
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N1", "content": "C1",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
            2: {"id": 2, "user_id": 1, "title": "N2", "content": "C2",
                "type": "system", "is_read": 1, "is_recalled": 0,
                "created_at": "2024-06-02 10:00:00"},
            3: {"id": 3, "user_id": 2, "title": "Other", "content": "C3",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-03 10:00:00"},
        }
        db._next_ids["notifications"] = 4

        resp = client.get("/api/notifications", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # User 1 should see N1 and N2 (both non-recalled), ordered by created_at DESC
        assert len(data["data"]) == 2
        assert data["total"] == 2
        assert data["data"][0]["id"] == 2  # most recent first
        assert data["data"][1]["id"] == 1

    def test_list_unread_only(self, client, db_with_user):
        """unread_only=true filters out read notifications."""
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N1", "content": "C1",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
            2: {"id": 2, "user_id": 1, "title": "N2", "content": "C2",
                "type": "system", "is_read": 1, "is_recalled": 0,
                "created_at": "2024-06-02 10:00:00"},
        }
        db._next_ids["notifications"] = 3

        resp = client.get("/api/notifications?unread_only=true", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["isRead"] is False  # bool

    def test_list_pagination(self, client, db_with_user):
        """page and page_size params are respected."""
        db = db_with_user
        db._tables["notifications"] = {
            i: {"id": i, "user_id": 1, "title": f"N{i}", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": f"2024-06-{i:02d} 10:00:00"}
            for i in range(1, 6)
        }
        db._next_ids["notifications"] = 6

        resp = client.get("/api/notifications?page=1&page_size=2", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["pageSize"] == 2

    def test_list_requires_auth(self, client):
        """No auth token returns 401."""
        resp = client.get("/api/notifications")
        assert resp.status_code == 401


class TestUnreadCount:
    """GET /api/notifications/unread-count"""

    def test_unread_zero(self, client, db_with_user):
        resp = client.get("/api/notifications/unread-count", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["count"] == 0

    def test_unread_nonzero(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N1", "content": "C1",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
            2: {"id": 2, "user_id": 1, "title": "N2", "content": "C2",
                "type": "system", "is_read": 1, "is_recalled": 0,
                "created_at": "2024-06-02 10:00:00"},
        }
        db._next_ids["notifications"] = 3

        resp = client.get("/api/notifications/unread-count", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["count"] == 1


class TestMarkAsRead:
    """PUT /api/notifications/{id}/read"""

    def test_mark_read_success(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N", "content": "C",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
        }
        db._next_ids["notifications"] = 2

        resp = client.put("/api/notifications/1/read", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "marked as read"
        # Verify the notification was updated
        assert db._tables["notifications"][1]["is_read"] == 1

    def test_mark_read_other_user(self, client, db_with_user):
        """Notification belonging to another user is silently not updated (still 200)."""
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 2, "title": "N", "content": "C",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
        }
        db._next_ids["notifications"] = 2

        resp = client.put("/api/notifications/1/read", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        # Notification was not updated (different user)
        assert db._tables["notifications"][1]["is_read"] == 0


class TestMarkAllRead:
    """PUT /api/notifications/read-all"""

    def test_mark_all_read(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N1", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
            2: {"id": 2, "user_id": 1, "title": "N2", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-02 10:00:00"},
            3: {"id": 3, "user_id": 2, "title": "N3", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-03 10:00:00"},
        }
        db._next_ids["notifications"] = 4

        resp = client.put("/api/notifications/read-all", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "all marked as read"
        # User 1's notifications are read, user 2's remain unread
        assert db._tables["notifications"][1]["is_read"] == 1
        assert db._tables["notifications"][2]["is_read"] == 1
        assert db._tables["notifications"][3]["is_read"] == 0


class TestClearAll:
    """DELETE /api/notifications/clear-all"""

    def test_clear_all(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N1", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
            2: {"id": 2, "user_id": 1, "title": "N2", "content": "",
                "type": "system", "is_read": 1, "is_recalled": 0,
                "created_at": "2024-06-02 10:00:00"},
            3: {"id": 3, "user_id": 2, "title": "N3", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-03 10:00:00"},
        }
        db._next_ids["notifications"] = 4

        resp = client.delete("/api/notifications/clear-all", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "cleared"
        # User 1's notifications are gone, user 2's remain
        assert 1 not in db._tables["notifications"]
        assert 2 not in db._tables["notifications"]
        assert 3 in db._tables["notifications"]


class TestDeleteNotification:
    """DELETE /api/notifications/{id}"""

    def test_delete_success(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
        }
        db._next_ids["notifications"] = 2

        resp = client.delete("/api/notifications/1", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "deleted"
        assert 1 not in db._tables["notifications"]

    def test_delete_not_found(self, client, db_with_user):
        resp = client.delete("/api/notifications/999", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 404

    def test_delete_other_user_notification(self, client, db_with_user):
        """Cannot delete another user's notification (returns 404)."""
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 2, "title": "N", "content": "",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
        }
        db._next_ids["notifications"] = 2

        resp = client.delete("/api/notifications/1", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 404


class TestCreateNotification:
    """POST /api/notifications — admin create"""

    def test_create_success(self, client, db_with_user):
        db = db_with_user
        resp = client.post("/api/notifications", json={
            "user_id": 1,
            "title": "Test",
            "content": "Hello",
            "type": "system",
        }, headers={"Authorization": f"Bearer {_admin_token()}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["message"] == "sent"
        assert data["data"]["id"] is not None
        # Verify notification was created in DB
        nid = data["data"]["id"]
        assert nid in db._tables["notifications"]
        assert db._tables["notifications"][nid]["title"] == "Test"

    def test_create_user_not_found(self, client, db_with_user):
        """Returns 404 when target user does not exist."""
        resp = client.post("/api/notifications", json={
            "user_id": 999,
            "title": "Test",
            "content": "Hello",
        }, headers={"Authorization": f"Bearer {_admin_token()}"})
        assert resp.status_code == 404

    def test_create_forbidden_for_regular_user(self, client, db_with_user):
        """Regular user gets 403."""
        resp = client.post("/api/notifications", json={
            "user_id": 1,
            "title": "Test",
            "content": "Hello",
        }, headers={"Authorization": f"Bearer {_user_token(1)}"})
        assert resp.status_code == 403

    def test_create_validation_error(self, client, db_with_user):
        """Missing required fields returns 422."""
        resp = client.post("/api/notifications", json={
            "user_id": 1,
            # no title
            "content": "Hello",
        }, headers={"Authorization": f"Bearer {_admin_token()}"})
        assert resp.status_code == 422

    def test_create_no_auth(self, client):
        resp = client.post("/api/notifications", json={
            "user_id": 1, "title": "T", "content": "C",
        })
        assert resp.status_code == 401


class TestBatchSend:
    """POST /api/notifications/batch — admin batch send"""

    def test_batch_to_specific_users(self, client, db_with_user):
        db = db_with_user
        db._tables["users"] = {
            1: {"id": 1}, 2: {"id": 2},
        }
        resp = client.post("/api/notifications/batch", json={
            "title": "Broadcast",
            "content": "To all",
            "type": "system",
            "user_ids": [1, 2],
        }, headers={"Authorization": f"Bearer {_admin_token()}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["count"] == 2
        # Verify both users got the notification
        notifs = list(db._tables["notifications"].values())
        assert len(notifs) == 2

    def test_batch_to_all(self, client, db_with_user):
        """Without user_ids, sends to all users."""
        db = db_with_user
        db._tables["users"] = {
            1: {"id": 1}, 2: {"id": 2}, 3: {"id": 3},
        }
        resp = client.post("/api/notifications/batch", json={
            "title": "Global",
            "content": "To everyone",
        }, headers={"Authorization": f"Bearer {_admin_token()}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["count"] == 3

    def test_batch_no_valid_users(self, client, db_with_user):
        """Returns 400 when no valid users found."""
        db = db_with_user
        db._tables["users"] = {}  # no users
        resp = client.post("/api/notifications/batch", json={
            "title": "Test",
            "content": "Content",
            "user_ids": [999],
        }, headers={"Authorization": f"Bearer {_admin_token()}"})
        assert resp.status_code == 400

    def test_batch_forbidden(self, client, db_with_user):
        """Regular user cannot batch send."""
        resp = client.post("/api/notifications/batch", json={
            "title": "Test",
            "content": "Content",
        }, headers={"Authorization": f"Bearer {_user_token(1)}"})
        assert resp.status_code == 403


class TestListSent:
    """GET /api/notifications/sent — admin sent list"""

    def test_list_sent(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N1", "content": "C1",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
            2: {"id": 2, "user_id": 2, "title": "N2", "content": "C2",
                "type": "system", "is_read": 0, "is_recalled": 1,
                "created_at": "2024-06-02 10:00:00"},  # recalled — excluded
        }
        db._next_ids["notifications"] = 3

        resp = client.get("/api/notifications/sent", headers={
            "Authorization": f"Bearer {_admin_token()}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 1  # only non-recalled
        assert data["total"] == 1

    def test_list_sent_forbidden(self, client, db_with_user):
        """Regular user cannot access sent list."""
        resp = client.get("/api/notifications/sent", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 403


class TestRecallNotification:
    """PUT /api/notifications/{id}/recall — admin recall"""

    def test_recall_success(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N", "content": "C",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
        }
        db._next_ids["notifications"] = 2

        resp = client.put("/api/notifications/1/recall", headers={
            "Authorization": f"Bearer {_admin_token()}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "recalled"
        assert db._tables["notifications"][1]["is_recalled"] == 1

    def test_recall_not_found(self, client, db_with_user):
        resp = client.put("/api/notifications/999/recall", headers={
            "Authorization": f"Bearer {_admin_token()}",
        })
        assert resp.status_code == 404

    def test_recall_forbidden(self, client, db_with_user):
        db = db_with_user
        db._tables["notifications"] = {
            1: {"id": 1, "user_id": 1, "title": "N", "content": "C",
                "type": "system", "is_read": 0, "is_recalled": 0,
                "created_at": "2024-06-01 10:00:00"},
        }
        db._next_ids["notifications"] = 2

        resp = client.put("/api/notifications/1/recall", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 403
