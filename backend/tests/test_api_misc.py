"""
Misc API tests — Patents, Conversion, Sidebar, and Health endpoints.

No PostgreSQL required. Uses the same MockDB pattern as test_api_auth.py.
"""

import json
import re
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ══════════════════════════════════════════════════════════════
#  Mock DB (shared between test classes)
# ══════════════════════════════════════════════════════════════


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

    @staticmethod
    def _extract_func(col: str) -> tuple[str, str | None]:
        """Extract SQL function name and inner column.
        Returns (inner_col, func_name). E.g. 'date(created_at)' → ('created_at', 'date').
        Also handles table prefix: 'date(s.created_at)' → ('created_at', 'date').
        Also handles PostgreSQL ::type cast: 'created_at::date' → ('created_at', 'date')."""
        c = col.split(".")[-1] if "." in col else col  # strip table alias first
        m = re.match(r'(\w+)\((\w+)\)', c)
        if m:
            return m.group(2), m.group(1).lower()
        # Handle PostgreSQL ::type cast syntax (e.g. created_at::date)
        cast_m = re.match(r'(\w+)::(\w+)', c)
        if cast_m:
            return cast_m.group(1), cast_m.group(2).lower()
        return c, None

    @staticmethod
    def _split_outside_parens(text: str, sep: str) -> list[str]:
        """Split on sep (case-insensitive) only at parenthesis depth 0."""
        parts: list[str] = []
        cur: list[str] = []
        depth = 0
        low = text.lower()
        sepl = sep.lower()
        i = 0
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            if depth == 0 and low.startswith(sepl, i):
                parts.append("".join(cur))
                cur = []
                i += len(sepl)
                continue
            cur.append(text[i])
            i += 1
        parts.append("".join(cur))
        return parts

    @staticmethod
    def _is_wrapping_paren(text: str) -> bool:
        """True if the outermost parens enclose the entire string."""
        depth = 0
        for i, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i < len(text) - 1:
                    return False
        return True

    def _where_conditions(self, sql: str) -> list:
        """Parse WHERE clause into list of condition groups (OR-of-ANDs).
        Returns list of groups, each group is list of (col, op, is_param, val, func) tuples.
        Supports parenthesized sub-expressions: '(A OR B) AND C' is expanded
        into OR-of-ANDs via distribution → [[A, C], [B, C]]."""
        if "WHERE" not in sql.upper():
            return []
        where_part = sql.split("WHERE", 1)[1].strip()
        where_part = self._strip_suffix(where_part)
        # Parse top-level AND terms; each term is either a leaf condition
        # or a nested OR-of-AND structure (from parentheses).
        terms: list[list[list]] = []
        for part in self._split_outside_parens(where_part, " and "):
            part = part.strip()
            if not part:
                continue
            while part.startswith("(") and part.endswith(")") and self._is_wrapping_paren(part):
                part = part[1:-1].strip()
            or_parts = [p.strip() for p in self._split_outside_parens(part, " or ")]
            or_parts = [p for p in or_parts if p]
            if len(or_parts) > 1:
                sub = []
                for clause in or_parts:
                    cond = self._parse_condition(clause)
                    if cond:
                        sub.append([cond])
                if sub:
                    terms.append(sub)
            else:
                cond = self._parse_condition(or_parts[0] if or_parts else part)
                if cond:
                    terms.append([[cond]])
        # Distribute nested OR groups into flat OR-of-ANDs (cartesian product)
        flat: list[list] = [[]]
        for term in terms:
            flat = [g + alt for g in flat for alt in term]
        return [g for g in flat if g]

    def _parse_condition(self, clause: str):
        """Parse a single leaf condition into (col, op, is_param, val, func) or None."""
        clause = clause.strip()
        while clause.startswith("(") and clause.endswith(")") and self._is_wrapping_paren(clause):
            clause = clause[1:-1].strip()
        if not clause:
            return None
        if " LIKE " in clause.upper():
            raw = self._strip_alias(clause.split()[0].strip().lower())
            col, func = self._extract_func(raw)
            val_part = clause.upper().split(" LIKE ")[1].strip()
            if val_part == "?":
                return (col, "LIKE", True, None, func)
            return (col, "LIKE", False, val_part.strip("'\""), func)
        elif " IN " in clause.upper():
            raw = self._strip_alias(clause.split()[0].strip().lower())
            col, func = self._extract_func(raw)
            in_part = clause.upper().split(" IN ")[1]
            num_q = in_part.count("?")
            return (col, "IN", True, num_q, func)
        elif "=?" in clause or "= ?" in clause:
            norm = clause.replace("= ?", "=?")
            raw = self._strip_alias(norm.split("=?")[0].strip().lower())
            col, func = self._extract_func(raw)
            right = norm.split("=?")[1].strip() if "=?" in norm else ""
            if right == "" or right == "?":
                return (col, "=", True, None, func)
            try:
                return (col, "=", False, int(right), func)
            except ValueError:
                return (col, "=", False, right.strip("'\""), func)
        elif "=" in clause:
            raw_raw, val_str = clause.split("=", 1)
            raw = self._strip_alias(raw_raw.strip().lower())
            col, func = self._extract_func(raw)
            val_str = val_str.strip()
            if val_str.startswith("'"):
                return (col, "=", False, val_str.strip("'"), func)
            try:
                return (col, "=", False, int(val_str), func)
            except ValueError:
                return (col, "=", False, val_str, func)
        return None

    @staticmethod
    def _apply_func(value, func: str | None):
        """Apply SQL function to a value for comparison."""
        if func is None or value is None:
            return value
        if func == "date":
            if isinstance(value, str):
                return value[:10]
            return value
        return value

    @staticmethod
    def _match_value(row_val: object, expected: object) -> bool:
        """Match row value against expected, handling date/timestamp comparisons."""
        if row_val == expected:
            return True
        # Handle date(ts_col) comparison: "2026-06-24 00:00:00" ≈ "2026-06-24"
        if isinstance(expected, str) and isinstance(row_val, str):
            if " " not in expected and " " in row_val and row_val.startswith(expected):
                return True
        return False

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
            for cond in group:
                col, op, is_param, val = cond[:4]
                func = cond[4] if len(cond) > 4 else None
                if op == "=":
                    actual = params[pi] if is_param else val
                    if is_param:
                        pi += 1
                    group_rows = [r for r in group_rows if self._match_value(self._apply_func(r.get(col), func), actual)]
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
            col_name = c.lower().strip()
            # Strip trailing " as alias" if present
            if col_name.endswith(" as"):
                col_name = col_name[:-4].strip()
            cols.append(col_name)
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
            self._last_result = [MockRow({"count(*)": len(rows), "cnt": len(rows)})]
            return

        limit, offset = self._limit_offset(sql, remaining)
        if offset or limit is not None:
            rows = rows[offset:(offset + limit) if limit else None]

        cols = self._select_cols(sql)
        if "*" in cols:
            explicit = [c for c in cols if c != "*"]
            if explicit:
                self._last_result = [MockRow({**r, **{c: r.get(c) for c in explicit}}) for r in rows]
            else:
                self._last_result = [MockRow(r.copy()) for r in rows]
        else:
            self._last_result = [MockRow({c: r.get(c) for c in cols}) for r in rows]

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
                    merged = r2.copy()
                    merged.update(r1)
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
                for cond in group:
                    col, op, is_param, val = cond[:4]
                    func = cond[4] if len(cond) > 4 else None
                    if op == "=":
                        actual = params[pi] if is_param else val
                        if is_param:
                            pi += 1
                        filtered = [r for r in filtered if self._match_value(self._apply_func(r.get(col), func), actual)]
                    elif op == "LIKE":
                        pattern = params[pi] if is_param else val
                        if is_param:
                            pi += 1
                        if isinstance(pattern, str) and pattern.startswith("%") and pattern.endswith("%"):
                            substr = pattern[1:-1].lower()
                            filtered = [r for r in filtered if substr in str(r.get(col, "")).lower()]
                        else:
                            filtered = [r for r in filtered if str(r.get(col, "")) == str(pattern)]
                for r in filtered:
                    matched_ids.add(all_joined.index(r))
            joined = [all_joined[i] for i in sorted(matched_ids)]
        else:
            joined = all_joined

        cols = self._select_cols(sql)
        if "*" in cols:
            # s.* or * expands to all columns; add any explicit columns too
            explicit = [c for c in cols if c != "*"]
            if explicit:
                self._last_result = [MockRow({**r, **{c: r.get(c) for c in explicit}}) for r in joined]
            else:
                self._last_result = [MockRow(r.copy()) for r in joined]
        else:
            self._last_result = [MockRow({c: r.get(c) for c in cols}) for r in joined]

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

    def rollback(self):
        pass

    def close(self):
        pass

    def __iter__(self):
        return iter(self._last_result)


# ══════════════════════════════════════════════════════════════
#  Shared fixtures
# ══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    return MockDB()


# ── Helpers ───────────────────────────────────────────────────


def _patch_all_get_db(monkeypatch, mock_db, *mod_names):
    """Patch get_db at definition site, auth, and specified module names.

    This ensures cached module-level references are updated per test.
    Modules without a get_db attribute (e.g. db_session-only modules)
    are tolerated via raising=False.
    """
    monkeypatch.setattr("app.database.get_db", lambda: mock_db)
    monkeypatch.setattr("app.auth.get_db", lambda: mock_db)
    for name in mod_names:
        monkeypatch.setattr(f"{name}.get_db", lambda: mock_db, raising=False)


def _user_token(user_id: int = 1) -> str:
    from app.auth import create_access_token
    return create_access_token({"user_id": user_id})


def _admin_token() -> str:
    from app.auth import create_access_token
    return create_access_token({"user_id": 0, "username": "admin"})


def _seed_user(mock_db, user_id: int = 1, is_superuser: bool = False) -> None:
    """Seed a user in the mock database for auth lookups."""
    if "users" not in mock_db._tables:
        mock_db._tables["users"] = {}
    mock_db._tables["users"][user_id] = {
        "id": user_id,
        "username": f"user{user_id}",
        "password_hash": "x",
        "is_superuser": is_superuser,
        "email": "",
        "is_active": 1,
        "created_at": "2024-01-01 00:00:00",
        "token_version": 0,
    }
    mock_db._next_ids["users"] = max(mock_db._next_ids.get("users", 1), user_id + 1)


# ══════════════════════════════════════════════════════════════
#  Patents API
# ══════════════════════════════════════════════════════════════


class TestPatentSearch:
    """GET /api/patents/search（纯本地数据库）"""

    @pytest.fixture
    def client(self, mock_db, monkeypatch):
        _patch_all_get_db(monkeypatch, mock_db, "app.api.patents")
        from app.api.patents import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @staticmethod
    def _patent_row(i, title, abstract, ipc="G06N", applicant="X", score=50):
        return {"id": i, "title": title, "abstract": abstract,
                "applicants": json.dumps([applicant], ensure_ascii=False),
                "inventors": json.dumps(["Y"], ensure_ascii=False),
                "filing_date": f"2024-{min(i, 12):02d}-01",
                "publication_date": "2024-12-01",
                "patent_number": f"CN{i}",
                "publication_number": f"CN{i}A",
                "ipc_codes": json.dumps([ipc]),
                "relevance_score": score}

    def test_search_empty(self, client, mock_db):
        """No patents returns empty list."""
        resp = client.get("/api/patents/search?q=")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_search_with_results(self, client, mock_db):
        """Keyword search matches local patents by title/abstract."""
        mock_db._tables["patents"] = {
            1: self._patent_row(1, "智能专利", "一种智能算法", score=95),
            2: self._patent_row(2, "其他技术", "无关内容", score=50),
        }
        mock_db._next_ids["patents"] = 3

        resp = client.get("/api/patents/search?q=智能")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["code"] == 200
        r = data["data"][0]
        assert "id" in r and "title" in r and "abstract" in r
        assert "applicants" in r and "inventors" in r
        # 不再返回供应商 source 字段
        assert "source" not in r

    def test_search_ignores_source_param(self, client, mock_db):
        """source 参数已删除，传入时被忽略，仍走本地检索"""
        mock_db._tables["patents"] = {
            1: self._patent_row(1, "P1", "A1", score=90),
        }
        mock_db._next_ids["patents"] = 2

        resp = client.get("/api/patents/search?q=&source=external")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 1
        assert "source" not in data["data"][0]

    def test_search_ipc_filter(self, client, mock_db):
        """IPC 分类号筛选"""
        mock_db._tables["patents"] = {
            1: self._patent_row(1, "P1", "A1", ipc="H01M"),
            2: self._patent_row(2, "P2", "A2", ipc="G06N"),
        }
        mock_db._next_ids["patents"] = 3

        resp = client.get("/api/patents/search?ipc_code=H01M")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["title"] == "P1"

    def test_search_applicant_filter(self, client, mock_db):
        """申请人筛选"""
        mock_db._tables["patents"] = {
            1: self._patent_row(1, "P1", "A1", applicant="华为"),
            2: self._patent_row(2, "P2", "A2", applicant="中兴"),
        }
        mock_db._next_ids["patents"] = 3

        resp = client.get("/api/patents/search?applicant=华为")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["title"] == "P1"

    def test_search_empty_query(self, client, mock_db):
        """Empty q returns all local patents (paginated)."""
        mock_db._tables["patents"] = {
            1: self._patent_row(1, "P1", "A1", score=90),
            2: self._patent_row(2, "P2", "A2", score=80),
        }
        mock_db._next_ids["patents"] = 3

        resp = client.get("/api/patents/search?q=")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 2

    def test_search_pagination(self, client, mock_db):
        """Page and page_size work with consistent total count."""
        mock_db._tables["patents"] = {
            i: self._patent_row(i, f"P{i}", f"A{i}", score=50 + i)
            for i in range(1, 6)
        }
        mock_db._next_ids["patents"] = 6

        resp = client.get("/api/patents/search?q=&page=1&page_size=2")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3  # ceil(5/2)

    def test_search_pagination_with_filter(self, client, mock_db):
        """总数与列表使用相同筛选条件"""
        mock_db._tables["patents"] = {
            i: self._patent_row(i, f"智能专利{i}", f"A{i}", score=i)
            for i in range(1, 6)
        }
        mock_db._next_ids["patents"] = 6

        resp = client.get("/api/patents/search?q=智能&page=2&page_size=2")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 5
        assert len(data["data"]) == 2
        assert data["page"] == 2

    def test_search_sort_whitelist(self, client, mock_db):
        """非法排序字段/方向回退到白名单默认值"""
        mock_db._tables["patents"] = {
            1: self._patent_row(1, "P1", "A1", score=10),
            2: self._patent_row(2, "P2", "A2", score=90),
        }
        mock_db._next_ids["patents"] = 3

        # 注入式排序字段不会拼进 SQL，回退为 relevance_score DESC
        resp = client.get(
            "/api/patents/search?q=&sort_by=title;DROP%20TABLE&order=weird"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"][0]["title"] == "P2"  # 按 relevance_score 降序

        resp = client.get("/api/patents/search?q=&sort_by=filing_date&order=asc")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"][0]["title"] == "P1"  # 按 filing_date 升序


class TestPatentDetail:
    """GET /api/patents/detail/{pid}（纯本地数据库）"""

    @pytest.fixture
    def client(self, mock_db, monkeypatch):
        _patch_all_get_db(monkeypatch, mock_db, "app.api.patents")
        from app.api.patents import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @staticmethod
    def _detail_row():
        return {"id": 42, "title": "发明", "abstract": "一种方法",
                "applicants": json.dumps(["某公司"]),
                "inventors": json.dumps(["某人"]),
                "filing_date": "2024-03-15",
                "publication_date": "2024-09-15",
                "patent_number": "CN999",
                "publication_number": "CN999A",
                "ipc_codes": json.dumps(["G06Q"]),
                "relevance_score": 88,
                "claims": "权利要求全文",
                "description": "说明书全文"}

    def test_detail_by_id(self, client, mock_db):
        mock_db._tables["patents"] = {42: self._detail_row()}
        mock_db._next_ids["patents"] = 43

        resp = client.get("/api/patents/detail/42")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["id"] == "42"
        assert data["data"]["title"] == "发明"
        assert data["data"]["patentNumber"] == "CN999"
        assert data["data"]["claims"] == "权利要求全文"
        assert data["data"]["description"] == "说明书全文"

    def test_detail_by_patent_number(self, client, mock_db):
        mock_db._tables["patents"] = {42: self._detail_row()}
        mock_db._next_ids["patents"] = 43

        resp = client.get("/api/patents/detail/CN999")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["patentNumber"] == "CN999"

    def test_detail_by_publication_number(self, client, mock_db):
        mock_db._tables["patents"] = {42: self._detail_row()}
        mock_db._next_ids["patents"] = 43

        resp = client.get("/api/patents/detail/CN999A")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == "42"

    def test_detail_not_found(self, client, mock_db):
        resp = client.get("/api/patents/detail/999")
        assert resp.status_code == 404
        assert "未找到" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════
#  Conversion API
# ══════════════════════════════════════════════════════════════


class TestConversionData:
    """GET /api/conversion/{task_id}"""

    @pytest.fixture
    def client(self, mock_db, monkeypatch):
        _patch_all_get_db(monkeypatch, mock_db, "app.api.conversion")
        from app.api.conversion import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_get_data_success(self, client, mock_db):
        """Returns solutions with evaluations and patent details."""
        _seed_user(mock_db, user_id=1)
        # Seed a task belonging to user 1
        mock_db._tables["tasks"] = {
            1: {"id": 1, "user_id": 1, "title": "测试任务",
                "description": "任务描述",
                "status": "completed", "created_at": "2024-06-01 10:00:00"},
        }
        mock_db._next_ids["tasks"] = 2

        # Seed solutions for this task
        mock_db._tables["solutions"] = {
            10: {"id": 10, "task_id": 1, "title": "方案A",
                 "description": "方案描述",
                 "principles": json.dumps(["TRIZ原理1"]),
                 "patent_references": json.dumps(["智能专利"]),
                 "confidence_score": 0.85,
                 "rating": 5},
        }
        mock_db._next_ids["solutions"] = 11

        # Seed evaluations
        mock_db._tables["evaluations"] = {
            100: {"id": 100, "solution_id": 10, "dimension": "创新性",
                  "score": 8, "details": "创新性很强"},
        }
        mock_db._next_ids["evaluations"] = 101

        # Seed workflow with agent5 output
        mock_db._tables["workflows"] = {
            1: {"id": 1, "task_id": 1,
                "steps": json.dumps([{
                    "agent_id": "agent5",
                    "output": json.dumps({
                        "patents": [{
                            "_title": "智能专利",
                            "patent_number": "CN123",
                            "applicants": "公司A",
                            "abstract": "智能专利摘要",
                        }],
                    }),
                }]),
                },
        }
        mock_db._next_ids["workflows"] = 2

        resp = client.get("/api/conversion/1", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["taskId"] == "1"
        assert len(data["data"]["solutions"]) == 1
        sol = data["data"]["solutions"][0]
        assert sol["id"] == "10"
        assert sol["title"] == "方案A"
        assert sol["confidenceScore"] == 0.85
        assert sol["evaluation"]["创新性"] == 8
        assert len(sol["refPatents"]) == 1
        assert sol["refPatents"][0]["_title"] == "智能专利"

    def test_get_data_not_found(self, client, mock_db):
        """Non-existent task returns 404."""
        _seed_user(mock_db, user_id=1)
        resp = client.get("/api/conversion/999", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 404

    def test_get_data_wrong_user(self, client, mock_db):
        """Task belonging to another user returns 404."""
        _seed_user(mock_db, user_id=1)
        mock_db._tables["tasks"] = {
            1: {"id": 1, "user_id": 2, "title": "Other's task",
                "description": "", "status": "completed",
                "created_at": "2024-06-01 10:00:00"},
        }
        mock_db._next_ids["tasks"] = 2

        resp = client.get("/api/conversion/1", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 404

    def test_get_data_requires_auth(self, client, mock_db):
        resp = client.get("/api/conversion/1")
        assert resp.status_code == 401


class TestCheckInfringement:
    """POST /api/conversion/{solution_id}/check-infringement"""

    @pytest.fixture
    def client(self, mock_db, monkeypatch):
        _patch_all_get_db(monkeypatch, mock_db, "app.api.conversion")

        # Mock AI chat completion to avoid real API calls
        async def mock_chat_completion(**kwargs):
            # 新签名返回信封：content 为 JSON 字符串
            return {
                "content": json.dumps({
                    "riskLevel": "中",
                    "riskScore": 65,
                    "analysisSummary": "存在中等侵权风险",
                    "claimOverlaps": [
                        {
                            "feature": "智能算法",
                            "patentClaim": "权利要求1",
                            "risk": "部分覆盖",
                            "suggestion": "修改算法细节",
                        },
                    ],
                    "designArounds": ["采用替代技术路线"],
                    "keyRecommendations": ["进行详细FTO分析"],
                }),
                "provider_id": "openai",
                "model_id": "gpt-4",
            }

        monkeypatch.setattr(
            "app.algorithm.ai_client.chat_completion",
            mock_chat_completion,
        )
        monkeypatch.setattr(
            "app.api.conversion.chat_completion",
            mock_chat_completion,
        )

        from app.api.conversion import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_check_success(self, client, mock_db):
        """AI infringement analysis returns structured result."""
        _seed_user(mock_db, user_id=1)
        mock_db._tables["tasks"] = {
            1: {"id": 1, "user_id": 1, "title": "T", "description": "",
                "status": "completed", "created_at": "2024-06-01 10:00:00"},
        }
        mock_db._next_ids["tasks"] = 2

        mock_db._tables["solutions"] = {
            10: {"id": 10, "task_id": 1, "title": "方案X",
                 "description": "一种智能处理方法",
                 "principles": json.dumps([]),
                 "patent_references": json.dumps(["参考专利"]),
                 "confidence_score": 0.8,
                 "rating": 4},
        }
        mock_db._next_ids["solutions"] = 11

        mock_db._tables["workflows"] = {
            1: {"id": 1, "task_id": 1,
                "steps": json.dumps([{
                    "agent_id": "agent5",
                    "output": json.dumps({
                        "patents": [{"_title": "参考专利", "patent_number": "CN456"}],
                    }),
                }]),
                },
        }
        mock_db._next_ids["workflows"] = 2

        resp = client.post("/api/conversion/10/check-infringement", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["riskLevel"] == "中"
        assert data["data"]["riskScore"] == 65
        assert len(data["data"]["claimOverlaps"]) == 1
        assert len(data["data"]["designArounds"]) == 1

    def test_check_solution_not_found(self, client, mock_db):
        """Non-existent solution returns 404."""
        _seed_user(mock_db, user_id=1)
        resp = client.post("/api/conversion/999/check-infringement", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 404

    def test_check_wrong_user(self, client, mock_db):
        """Solution belonging to another user returns 404."""
        _seed_user(mock_db, user_id=1)
        mock_db._tables["tasks"] = {
            1: {"id": 1, "user_id": 2, "title": "T", "description": "",
                "status": "completed", "created_at": "2024-06-01 10:00:00"},
        }
        mock_db._next_ids["tasks"] = 2

        mock_db._tables["solutions"] = {
            10: {"id": 10, "task_id": 1, "title": "方案X",
                 "description": "",
                 "principles": json.dumps([]),
                 "patent_references": json.dumps([]),
                 "confidence_score": 0.5,
                 "rating": 3},
        }
        mock_db._next_ids["solutions"] = 11

        resp = client.post("/api/conversion/10/check-infringement", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 404

    def test_check_no_patents_fallback(self, client, mock_db):
        """When no patents found, returns friendly fallback without calling AI."""
        _seed_user(mock_db, user_id=1)
        mock_db._tables["tasks"] = {
            1: {"id": 1, "user_id": 1, "title": "T", "description": "",
                "status": "completed", "created_at": "2024-06-01 10:00:00"},
        }
        mock_db._next_ids["tasks"] = 2

        mock_db._tables["solutions"] = {
            10: {"id": 10, "task_id": 1, "title": "方案Y",
                 "description": "描述",
                 "principles": json.dumps([]),
                 "patent_references": json.dumps(["不存在的专利"]),
                 "confidence_score": 0.7,
                 "rating": 4},
        }
        mock_db._next_ids["solutions"] = 11

        # No workflow data → no patents matched
        resp = client.post("/api/conversion/10/check-infringement", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["riskLevel"] == "无法分析"
        assert data["data"]["riskScore"] == 0

    def test_check_requires_auth(self, client, mock_db):
        resp = client.post("/api/conversion/1/check-infringement")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════
#  Sidebar API
# ══════════════════════════════════════════════════════════════


class TestSidebarStats:
    """GET /api/sidebar/stats"""

    @pytest.fixture
    def client(self, mock_db, monkeypatch):
        _patch_all_get_db(monkeypatch, mock_db, "app.api.sidebar")

        from app.api.sidebar import router

        app = FastAPI()
        app.include_router(router)
        return app, TestClient(app)

    def test_stats_regular_user(self, client, mock_db):
        """Regular user sees only their own task stats."""
        _seed_user(mock_db, user_id=1)
        mock_db._tables["tasks"] = {
            1: {"id": 1, "user_id": 1, "title": "T1",
                "status": "completed", "created_at": datetime_today()},
            2: {"id": 2, "user_id": 1, "title": "T2",
                "status": "analyzing", "created_at": "2024-05-01 10:00:00"},
            3: {"id": 3, "user_id": 2, "title": "Other",
                "status": "completed", "created_at": datetime_today()},
        }
        mock_db._next_ids["tasks"] = 4

        resp = client[1].get("/api/sidebar/stats", headers={
            "Authorization": f"Bearer {_user_token(1)}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["todayTasks"] == 1  # only user 1's today tasks
        assert data["data"]["completedTasks"] == 1  # only user 1's completed
        assert data["data"]["analyzingTasks"] == 1
        assert data["data"]["patentCount"] == 0  # non-admin sees 0

    def test_stats_admin(self, client, mock_db):
        """Admin sees global task stats and patent count."""
        _seed_user(mock_db, user_id=0, is_superuser=True)
        mock_db._tables["tasks"] = {
            1: {"id": 1, "user_id": 1, "title": "T1",
                "status": "completed", "created_at": datetime_today()},
            2: {"id": 2, "user_id": 2, "title": "T2",
                "status": "analyzing", "created_at": datetime_today()},
        }
        mock_db._next_ids["tasks"] = 3

        mock_db._tables["patents"] = {
            1: {"id": 1, "title": "P1", "abstract": "",
                "applicants": "[]", "inventors": "[]",
                "filing_date": "", "publication_date": "",
                "patent_number": "", "ipc_codes": "[]",
                "relevance_score": 0},
        }
        mock_db._next_ids["patents"] = 2

        resp = client[1].get("/api/sidebar/stats", headers={
            "Authorization": f"Bearer {_user_token(0, 'admin')}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["todayTasks"] == 2  # all tasks today
        assert data["data"]["completedTasks"] == 1
        assert data["data"]["analyzingTasks"] == 1
        assert data["data"]["patentCount"] == 1  # admin sees patent count

    def test_stats_no_auth(self, client, mock_db):
        """No token returns 401."""
        app, test_client = client
        resp = test_client.get("/api/sidebar/stats")
        assert resp.status_code == 401


def datetime_today() -> str:
    """Return today's date in YYYY-MM-DD HH:MM:SS format for mock DB."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d 00:00:00")


# ══════════════════════════════════════════════════════════════
#  Health API
# ══════════════════════════════════════════════════════════════


class TestHealth:
    """GET /api/health"""

    @pytest.fixture
    def client(self, mock_db, monkeypatch):
        _patch_all_get_db(monkeypatch, mock_db)

        from app.main import health_check

        app = FastAPI()
        app.get("/api/health")(health_check)
        return TestClient(app)

    def test_health_ok(self, client):
        """Health endpoint returns 200 with checks."""
        resp = client.get("/api/health")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Overall status should be at least 'healthy' or possibly 'degraded'
        # depending on disk/memory, but should always return
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"]["status"] == "ok"
        assert "disk" in data["checks"]
        assert "memory" in data["checks"]
