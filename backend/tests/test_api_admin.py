"""
Admin API tests — mock DB and service layer.

Tests all 33 admin endpoints across 5 router groups:
  Monitor (4), Users (4), Patents (6), Settings (5), Providers (14)

Strategy:
  - Use a real in-memory MockDB (multi-table, basic SQL support) for DB-heavy routes
  - Mock model_service + ModelsCrudService for provider routes
  - Override all auth dependencies to return an admin user
  - Patch module-level imports of get_db/model_service for each sub-module
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

class MockRow(dict):
    """Mock row supporting both dict and integer indexing."""


# ═══════════════════════════════════════════════════════════════════════════════
#  MockDB — in-memory multi-table database
# ═══════════════════════════════════════════════════════════════════════════════


class MockDB:
    """In-memory mock database supporting multiple tables.

    Handles common SQL patterns used by admin endpoints:
      SELECT ... FROM table [WHERE ...] [GROUP BY ...] [ORDER BY ...] [LIMIT/OFFSET]
      INSERT INTO table (...) VALUES (...) [RETURNING ...]
      UPDATE table SET ... WHERE ...
      DELETE FROM table WHERE ...

    Supports aggregate functions: COUNT, AVG, SUM, COALESCE.
    Handles ``col=?``, ``col = ?``, ``col='literal'``, and ``col IN (?,?,?)``.
    """

    def __init__(self):
        self._tables: dict[str, dict[int, dict]] = {}
        self._next_ids: dict[str, int] = {}
        self._last_result: list[MockRow] = []

    # ── helpers ──────────────────────────────────────────────────────────

    def _table(self, name: str) -> dict[int, dict]:
        if name not in self._tables:
            self._tables[name] = {}
            self._next_ids[name] = 1
        return self._tables[name]

    def _next_id(self, table: str) -> int:
        tid = self._next_ids.get(table, 1)
        self._next_ids[table] = tid + 1
        return tid

    @staticmethod
    def _extract_table_name(sql: str) -> str | None:
        # SELECT … FROM table
        m = re.search(r"\bFROM\s+(\w+)", sql, re.IGNORECASE)
        if m:
            return m.group(1)
        # INSERT INTO table
        m = re.search(r"INSERT\s+INTO\s+(\w+)", sql, re.IGNORECASE)
        if m:
            return m.group(1)
        # UPDATE table
        m = re.search(r"UPDATE\s+(\w+)", sql, re.IGNORECASE)
        if m:
            return m.group(1)
        # DELETE FROM table
        m = re.search(r"DELETE\s+FROM\s+(\w+)", sql, re.IGNORECASE)
        return m.group(1) if m else None

    def _parse_where(self, sql: str, params: tuple | list | None) -> dict:
        """Parse WHERE conditions → {col: value}.

        Supports ``col=?``, ``col = ?``, ``col='literal'``, and ``col IN (?,?,?)``.
        Only uses *params* for ``?`` placeholders.
        """
        where: dict = {}
        if "WHERE" not in sql:
            return where
        parts = sql.split("WHERE", 1)
        if len(parts) < 2:
            return where
        conditions = parts[1].strip()
        # Strip clauses after WHERE that aren't conditions
        for keyword in ("ORDER", "LIMIT", "GROUP", "HAVING"):
            idx = re.search(rf"\b{keyword}\b", conditions, re.IGNORECASE)
            if idx:
                conditions = conditions[: idx.start()]

        # Track consumed param count
        param_idx = 0

        # Handle `col IN (?,?,?)` — count placeholders, consume params
        in_pattern = re.compile(r"(\w+(?:\.\w+)?)\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
        for m in in_pattern.finditer(conditions):
            col, placeholders = m.group(1), m.group(2)
            if "." in col:
                col = col.split(".")[-1]
            n = placeholders.count("?")
            if n > 0 and params is not None and param_idx + n <= len(params):
                where[col] = list(params[param_idx : param_idx + n])
                param_idx += n

        # Handle individual conditions (split on AND, but not inside IN)
        cleaned = in_pattern.sub("", conditions)
        clauses = re.split(r"\bAND\b", cleaned, flags=re.IGNORECASE)

        # Collect OR-group constraints: {col: value} from OR branches
        or_groups: list[dict] = []

        for clause in clauses:
            clause = clause.strip().lstrip("(").rstrip(")")
            if not clause:
                continue

            # Check if this clause is an OR expression
            or_parts = re.split(r"\bOR\b", clause, flags=re.IGNORECASE)
            is_or = len(or_parts) > 1

            if is_or:
                # Collect all OR branch constraints
                for or_part in or_parts:
                    or_part = or_part.strip()
                    constraint = self._parse_simple_condition(or_part, params, param_idx)
                    if constraint is not None:
                        col, val, consumed = constraint
                        or_groups.append({col: val})
                        param_idx += consumed
                continue

            # Simple (non-OR) condition
            constraint = self._parse_simple_condition(clause, params, param_idx)
            if constraint is not None:
                col, val, consumed = constraint
                where[col] = val
                param_idx += consumed

        if or_groups:
            where["__or__"] = or_groups
        return where

    @staticmethod
    def _strip_cast(col: str) -> str:
        """Strip PostgreSQL ::type cast suffix from column name.
        E.g. 'created_at::date' → 'created_at'."""
        if "::" in col:
            col = col.split("::")[0]
        return col

    def _parse_simple_condition(self, expr: str, params, start_idx: int) -> tuple | None:
        """Parse a single condition like col=? or col LIKE ?.
        Returns (column_or_key, value, consumed_count) or None if no match.
        Column may be a plain string or ("__gt__", col) tuple for > constraints."""
        expr = expr.strip()
        # col LIKE ? (param-based) — keep % wildcard in value for substring matching
        like_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s+LIKE\s+\?", expr, re.IGNORECASE)
        if like_m:
            col = self._strip_cast(like_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            if params is not None and start_idx < len(params):
                return (col, params[start_idx], 1)
            return (col, "", 0)
        # col=? / col = ? (param-based)
        eq_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s*=\s*\?", expr)
        if eq_m:
            col = self._strip_cast(eq_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            if params is not None and start_idx < len(params):
                return (col, params[start_idx], 1)
            return (col, None, 0)
        # col='literal' (hardcoded string)
        lit_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s*=\s*'([^']*)'", expr)
        if lit_m:
            col = self._strip_cast(lit_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            return (col, lit_m.group(2), 0)
        # col=NUMBER (unquoted numeric literal)
        num_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s*=\s*(\d+)", expr)
        if num_m:
            col = self._strip_cast(num_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            return (col, int(num_m.group(2)), 0)
        # col > NUMBER (unquoted numeric comparison)
        gt_num_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s*>\s*(\d+)", expr)
        if gt_num_m:
            col = self._strip_cast(gt_num_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            return (("__gt__", col), int(gt_num_m.group(2)), 0)
        # col > ? (param-based)
        gt_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s*>\s*\?", expr)
        if gt_m:
            col = self._strip_cast(gt_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            if params is not None and start_idx < len(params):
                return (("__gt__", col), params[start_idx], 1)
            return (("__gt__", col), 0, 0)
        # col >= ? (param-based)
        gte_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s*>=\s*\?", expr)
        if gte_m:
            col = self._strip_cast(gte_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            if params is not None and start_idx < len(params):
                return (col, params[start_idx], 1)
            return (col, None, 0)
        # col >= NUMBER (unquoted numeric literal)
        gte_num_m = re.match(r"(\w+(?:\.\w+)?(?:::\w+)?)\s*>=\s*(\d+)", expr)
        if gte_num_m:
            col = self._strip_cast(gte_num_m.group(1))
            if "." in col:
                col = col.split(".")[-1]
            return (col, int(gte_num_m.group(2)), 0)
        return None

    def _apply_where(self, rows: list[dict], where: dict) -> list[dict]:
        result = list(rows)

        # Extract OR constraints first (disjunctive)
        or_groups = where.pop("__or__", None)

        # Apply regular AND constraints
        for key, val in where.items():
            if isinstance(key, tuple) and key[0] == "__gt__":
                col = key[1]
                result = [r for r in result if (r.get(col) or 0) > val]
            elif isinstance(val, list):
                result = [r for r in result if r.get(key) in val]
            elif isinstance(key, tuple) and key[0] == "__like__":
                col = key[1]
                pattern = val if isinstance(val, str) else ""
                result = [r for r in result if pattern.lower() in str(r.get(col, "")).lower()]
            elif isinstance(val, str):
                # Check if LIKE pattern
                if "%" in val:
                    pattern = val.replace("%", "")
                    result = [r for r in result if pattern.lower() in str(r.get(key, "")).lower()]
                else:
                    result = [r for r in result if r.get(key) == val]
            else:
                result = [r for r in result if r.get(key) == val]

        # Apply OR constraints (disjunctive) — a row matches if any OR branch matches
        if or_groups:
            or_result = []
            for row in result:
                for or_branch in or_groups:
                    match = True
                    for col, val in or_branch.items():
                        # LIKE pattern matching
                        if isinstance(val, str) and "%" in val:
                            pattern = val.replace("%", "")
                            if pattern.lower() not in str(row.get(col, "")).lower():
                                match = False
                                break
                        elif isinstance(val, tuple) and val[0] == "__like__":
                            pattern = str(val[1]).replace("%", "") if val[1] else ""
                            if pattern.lower() not in str(row.get(col, "")).lower():
                                match = False
                                break
                        else:
                            if row.get(col) != val:
                                match = False
                                break
                    if match:
                        or_result.append(row)
                        break
            result = or_result

        return result

    @staticmethod
    def _extract_aggregate_col(sql: str, func: str) -> str | None:
        m = re.search(rf"{func}\(\s*(?:\w+\.)?(\w+)\s*\)", sql, re.IGNORECASE)
        return m.group(1) if m else None

    def _has_aggregate(self, sql: str) -> str | None:
        for func in ("COUNT", "AVG", "SUM", "COALESCE"):
            # Word-boundary + function-call check to avoid matching "request_count"
            if re.search(rf"\b{func}\s*\(", sql, re.IGNORECASE):
                return func
        return None

    def _build_result_for_aggregate(self, func: str, sql: str, rows: list[dict]) -> list[MockRow]:
        if func == "COUNT":
            return [MockRow({0: len(rows), "count": len(rows)})]

        if func == "AVG":
            col = self._extract_aggregate_col(sql, "AVG")
            if col:
                vals = [r.get(col, 0) or 0 for r in rows if r.get(col) is not None and (r.get(col) or 0) > 0]
                avg = sum(vals) / len(vals) if vals else None
                return [MockRow({0: avg if avg is not None else 0, "avg": avg})]
            return [MockRow({0: 0})]

        if func in ("SUM",):
            col = self._extract_aggregate_col(sql, "SUM")
            if col:
                total = sum(r.get(col, 0) or 0 for r in rows)
                return [MockRow({0: total, "sum": total})]
            return [MockRow({0: 0})]

        if func == "COALESCE":
            sum_col = self._extract_aggregate_col(sql, "SUM")
            if sum_col:
                total = sum(r.get(sum_col, 0) or 0 for r in rows)
                return [MockRow({0: total, "coalesce": total})]
            return [MockRow({0: 0, "coalesce": 0})]

        return [MockRow({0: 0})]

    # ── execute ──────────────────────────────────────────────────────────

    def execute(self, sql: str, params: tuple | list | None = None):
        self._last_result = []
        sql_stripped = sql.strip()
        upper = sql_stripped.upper()

        if upper.startswith("SELECT"):
            self._handle_select(sql_stripped, params)
        elif upper.startswith("INSERT"):
            self._handle_insert(sql_stripped, params)
        elif upper.startswith("UPDATE"):
            self._handle_update(sql_stripped, params)
        elif upper.startswith("DELETE"):
            self._handle_delete(sql_stripped, params)
        return self

    def _handle_select(self, sql: str, params):
        # PostgreSQL-specific functions → not available in mock
        if "pg_database_size" in sql or "current_database" in sql:
            raise RuntimeError("pg_database_size unavailable in mock")

        table_name = self._extract_table_name(sql)
        if not table_name:
            return

        # JOIN queries → return empty (mock doesn't support cross-table joins)
        if " JOIN " in sql.upper():
            self._last_result = []
            return

        table = self._table(table_name)
        rows = list(table.values())

        where = self._parse_where(sql, params)
        rows = self._apply_where(rows, where)

        # ── Aggregates ───────────────────────────────────────────────────
        agg_func = self._has_aggregate(sql)
        if agg_func:
            if "GROUP BY" in sql.upper():
                gb_m = re.search(
                    r"GROUP\s+BY\s+((?:\w+(?:::\w+)?(?:\s*\([^)]*\s*\))?(?:\s*,\s*)?)+)",
                    sql, re.IGNORECASE,
                )
                if gb_m:
                    gb_expr = gb_m.group(1).split(",")[0].strip()
                    # Extract actual column name from function call: date(created_at) → created_at
                    # Also handle PostgreSQL ::type cast: created_at::date → created_at
                    gb_name = gb_expr
                    if "(" in gb_expr:
                        inner = gb_expr.split("(")[1]
                        gb_name = inner.rstrip(")") if ")" in inner else inner
                    elif "::" in gb_expr:
                        gb_name = gb_expr.split("::")[0]
                    else:
                        gb_name = gb_expr

                    # Detect aliases in SELECT clause
                    select_part = sql.split("FROM")[0] if "FROM" in sql.upper() else ""
                    # Remove COUNT(*) to focus on the grouping column alias
                    non_cnt_part = re.sub(
                        r"COUNT\s*\(\s*\*\s*\)\s*(?:AS\s+)?\w+\s*,?\s*", "", select_part, flags=re.IGNORECASE
                    )
                    # Remove any trailing comma and strip
                    non_cnt_clean = non_cnt_part.strip().rstrip(",").strip()
                    alias_m = re.search(r"(?:AS\s+)?(\w+)\s*$", non_cnt_clean, re.IGNORECASE)
                    group_alias = alias_m.group(1) if alias_m else gb_name

                    # Alias for COUNT(*) column
                    cnt_m = re.search(r"COUNT\s*\(\s*\*\s*\)\s+(?:AS\s+)?(\w+)", sql, re.IGNORECASE)
                    cnt_alias = cnt_m.group(1) if cnt_m else "cnt"

                    groups: dict = {}
                    for row in rows:
                        key = row.get(gb_name)
                        if key is not None:
                            str_key = str(key)[:10]  # Truncate for date grouping
                        else:
                            str_key = ""
                        if str_key not in groups:
                            groups[str_key] = []
                        groups[str_key].append(row)
                    result_rows = []
                    for s_key, group in groups.items():
                        result: dict = {group_alias: s_key, cnt_alias: len(group)}
                        result_rows.append(MockRow(result))
                    self._last_result = result_rows
                    return
                self._last_result = [MockRow(r.copy()) for r in rows]
                return
            self._last_result = self._build_result_for_aggregate(agg_func, sql, rows)
            return

        # ── ORDER BY ─────────────────────────────────────────────────────
        order_m = re.search(r"ORDER\s+BY\s+(\w+(?:\.\w+)?)\s*(DESC|ASC)?", sql, re.IGNORECASE)
        if order_m:
            col = order_m.group(1)
            if "." in col:
                col = col.split(".")[-1]
            desc = (order_m.group(2) or "").upper() == "DESC"
            rows = sorted(
                rows,
                key=lambda r, c=col: (r.get(c) if r.get(c) is not None else ""),
                reverse=desc,
            )

        # ── LIMIT / OFFSET ───────────────────────────────────────────────
        limit: int | None = None
        offset = 0
        limit_m = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
        if limit_m:
            limit = int(limit_m.group(1))
        else:
            # LIMIT ? placeholder — resolve from remaining params
            lim_q = re.search(r"LIMIT\s+\?", sql, re.IGNORECASE)
            if lim_q and params and len(params) > 0:
                if "OFFSET" in sql.upper() and len(params) >= 2:
                    limit = int(params[-2])
                    offset = int(params[-1])
                else:
                    limit = int(params[-1])
        offset_m = re.search(r"OFFSET\s+(\d+)", sql, re.IGNORECASE)
        if offset_m:
            offset = int(offset_m.group(1))

        if limit is not None:
            rows = rows[offset : offset + limit]
        elif offset:
            rows = rows[offset:]

        self._last_result = [MockRow(r.copy()) for r in rows]

    def _handle_insert(self, sql: str, params):
        table_name = self._extract_table_name(sql)
        if not table_name:
            return
        table = self._table(table_name)

        cols_m = re.search(r"\(([^)]+)\)\s*VALUES", sql, re.IGNORECASE)
        if not cols_m:
            return
        cols = [c.strip().strip('"') for c in cols_m.group(1).split(",")]

        row_id = self._next_id(table_name)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row: dict = {"id": row_id}
        if params:
            for i, col in enumerate(cols):
                if i < len(params):
                    row[col] = params[i]
        if "created_at" not in row:
            row["created_at"] = now

        table[row_id] = row

        if "RETURNING" in sql:
            ret_part = sql.split("RETURNING")[1].strip()
            ret_cols = [c.strip() for c in ret_part.split(",")]
            ret_row = {c: row.get(c) for c in ret_cols}
            self._last_result = [MockRow(ret_row)]

    def _handle_update(self, sql: str, params):
        table_name = self._extract_table_name(sql)
        if not table_name:
            return
        table = self._table(table_name)

        if "SET" not in sql:
            return

        set_str = sql.split("SET")[1]
        where_str = set_str.split("WHERE")[1] if "WHERE" in set_str else ""
        set_part = set_str.split("WHERE")[0] if "WHERE" in set_str else set_str

        # Parse SET assignments → list of (col_name, is_param, literal_or_none)
        set_items: list[tuple[str, bool, str | None]] = []
        for assignment in set_part.split(","):
            assignment = assignment.strip()
            if "=" not in assignment:
                continue
            col = assignment.split("=", 1)[0].strip()
            rhs = assignment.split("=", 1)[1].strip()
            if rhs in ("?", "?"):
                set_items.append((col, True, None))  # param-based
            else:
                set_items.append((col, False, rhs))  # literal expression

        # Consume params for param-based SET items, rest go to WHERE
        param_idx = 0
        param_set_count = sum(1 for it in set_items if it[1])
        where_params: tuple | list = ()
        if params:
            # param-based SET values come first
            set_params = params[:param_set_count] if param_set_count <= len(params) else params
            where_params = params[param_set_count:] if param_set_count < len(params) else ()
            param_idx = 0
        else:
            set_params = ()

        # Build SET values
        set_vals: list[tuple[str, object]] = []
        expr_vals: list[tuple[str, str, str, int]] = []  # (col, operand_col, op, amount)
        for item in set_items:
            col, is_param, literal = item
            if is_param:
                if param_idx < len(set_params):
                    set_vals.append((col, set_params[param_idx]))
                    param_idx += 1
            elif literal:
                # Handle arithmetic expressions: token_version + 1
                if "+" in literal:
                    parts = literal.split("+")
                    operand = parts[0].strip()
                    amount = int(parts[1].strip())
                    expr_vals.append((col, operand, "+", amount))
                elif "-" in literal:
                    parts = literal.split("-")
                    operand = parts[0].strip()
                    amount = int(parts[1].strip())
                    expr_vals.append((col, operand, "-", amount))

        # Parse WHERE with remaining params
        where = {}
        if where_str:
            where = self._parse_where(f"WHERE {where_str}", list(where_params) if where_params else None)

        # Apply updates
        for row in table.values():
            if where and not all(row.get(col) == val for col, val in where.items()):
                continue
            for col, val in set_vals:
                row[col] = val
            for col, operand_col, op, amount in expr_vals:
                current = row.get(operand_col, 0)
                if not isinstance(current, (int, float)):
                    current = 0
                if op == "+":
                    row[col] = current + amount
                elif op == "-":
                    row[col] = current - amount

    def _handle_delete(self, sql: str, params):
        table_name = self._extract_table_name(sql)
        if not table_name:
            return
        table = self._table(table_name)
        where = self._parse_where(sql, params)

        to_del = []
        for rid, row in table.items():
            if all(row.get(col) == val for col, val in where.items()):
                to_del.append(rid)
        for rid in to_del:
            del table[rid]

    # ── cursor API ───────────────────────────────────────────────────────

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

    # ── test helpers ─────────────────────────────────────────────────────

    def add_row(self, table: str, **cols) -> dict:
        t = self._table(table)
        row_id = self._next_id(table)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row: dict = {"id": row_id, **cols}
        if "created_at" not in row:
            row["created_at"] = now
        t[row_id] = row
        return row


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def client(mock_db, monkeypatch):
    """TestClient with admin router, all deps overridden, and module-level patches."""
    # ── Step 1: Import modules that have module-level imports of get_db/model_service ──
    import app.api.admin.monitor as monitor_mod
    import app.api.admin.patent_db as patent_mod
    import app.api.admin.settings as settings_mod
    import app.api.admin.providers as providers_mod
    import app.algorithm.model_service as model_svc_mod
    import app.database as db_mod

    # ── Step 2: Patch module-level get_db references ──
    monkeypatch.setattr(monitor_mod, "get_db", lambda: mock_db)
    monkeypatch.setattr(patent_mod, "get_db", lambda: mock_db)
    monkeypatch.setattr(settings_mod, "get_db", lambda: mock_db)
    monkeypatch.setattr(db_mod, "get_db", lambda: mock_db)

    # ── Step 3: Create a default mock model_service ──
    mock_svc = MagicMock()
    monkeypatch.setattr(providers_mod, "model_service", mock_svc)
    monkeypatch.setattr(model_svc_mod, "model_service", mock_svc)

    # ── Step 4: Build the FastAPI test app ──
    import app.api.deps as deps_mod
    from app.api.admin import router as admin_router
    from app.auth import require_admin
    from app.auth.instance import current_active_user, current_superuser
    from app.db.models import User as OrmUser
    from app.db.session import get_session

    test_app = FastAPI()
    test_app.include_router(admin_router)

    # 真实管理员（FastAPI Users 路径 — 返回 ORM User）
    orm_admin = OrmUser(
        id=1, email="admin@example.com",
        hashed_password="!", is_active=True, is_superuser=True, is_verified=True,
        username="admin", token_version=0,
    )
    # 旧 require_admin 垫片路径 — 返回 dict
    admin_dict = {
        "id": 1, "username": "admin", "is_superuser": True,
        "email": "admin@example.com", "is_active": True, "created_at": "",
    }

    # 业务表仍走 mock_db
    test_app.dependency_overrides[deps_mod.get_db_dep] = lambda: mock_db
    # admin/users 等 ORM 路由：get_session 直接被 ORM 路由用，必须也覆盖
    test_app.dependency_overrides[get_session] = lambda: mock_db
    # FastAPI Users 依赖（auth.instance 里定义的两个）
    test_app.dependency_overrides[current_active_user] = lambda: orm_admin
    test_app.dependency_overrides[current_superuser] = lambda: orm_admin
    # deps.py 里 CurrentUser/SuperUserDep 是 import-time 别名，必须替换符号本身
    deps_mod.CurrentUser = lambda: orm_admin
    deps_mod.SuperUserDep = lambda: orm_admin
    test_app.dependency_overrides[require_admin] = lambda: admin_dict

    client = TestClient(test_app)
    client._mock_svc = mock_svc  # expose for tests to configure
    return client


# ═══════════════════════════════════════════════════════════════════════════════
#  Monitor endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestMonitor:
    """GET /api/admin/monitor/*"""

    def test_overview_with_data(self, client, mock_db):
        mock_db.add_row("tasks", user_id=1, status="completed", created_at="2024-01-01")
        mock_db.add_row("tasks", user_id=1, status="failed", created_at="2024-01-02")
        mock_db.add_row("tasks", user_id=2, status="completed", created_at="2024-01-03")
        mock_db.add_row("analyses", task_id=1)
        mock_db.add_row("solutions", task_id=1, rating=4)
        mock_db.add_row("solutions", task_id=2, rating=5)

        resp = client.get("/api/admin/monitor/overview")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["totalTasks"] == 3
        assert data["completedTasks"] == 2
        assert data["failedTasks"] == 1
        assert data["successRate"] == 66.7
        assert data["totalAnalyses"] == 1
        assert data["totalSolutions"] == 2
        assert data["avgRating"] == 4.5

    def test_overview_empty(self, client):
        resp = client.get("/api/admin/monitor/overview")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["totalTasks"] == 0
        assert data["completedTasks"] == 0
        assert data["failedTasks"] == 0
        assert data["successRate"] == 0
        assert data["totalAnalyses"] == 0
        assert data["totalSolutions"] == 0
        assert data["avgRating"] == 0

    def test_tasks_with_data(self, client, mock_db):
        mock_db.add_row("tasks", user_id=1, status="completed", created_at="2024-06-20")
        mock_db.add_row("tasks", user_id=1, status="completed", created_at="2024-06-21")
        mock_db.add_row("tasks", user_id=1, status="failed", created_at="2024-06-22")
        mock_db.add_row("tasks", user_id=2, status="pending", created_at="2024-06-23")

        resp = client.get("/api/admin/monitor/tasks")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "byStatus" in data
        assert "recent7days" in data

    def test_keys_with_data(self, client, mock_db):
        mock_db.add_row("api_keys", key_name="key1", request_count=100, current_rpm=5, max_rpm=60, is_active=1)
        mock_db.add_row("api_keys", key_name="key2", request_count=50, current_rpm=2, max_rpm=30, is_active=1)
        mock_db.add_row("api_keys", key_name="key3", request_count=0, current_rpm=0, max_rpm=60, is_active=0)

        resp = client.get("/api/admin/monitor/keys")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["totalKeys"] == 3
        assert data["activeKeys"] == 2
        assert data["totalRequests"] == 150
        assert len(data["keyUsage"]) == 3

    def test_system_status(self, client, mock_db):
        mock_db.add_row("users", username="admin", is_superuser=True)
        mock_db.add_row("tasks", user_id=1, status="completed")
        mock_db.add_row("patents", title="test patent")

        resp = client.get("/api/admin/monitor/system")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "uptime" in data
        assert "version" in data
        assert "pythonVersion" in data
        assert "platform" in data
        assert data["totalUsers"] >= 1
        assert data["totalTasks"] >= 1
        assert data["totalPatents"] >= 1
        assert "apiKeys" in data
        assert "memory" in data
        assert "cpu" in data
        assert "aiStats" in data
        assert "dbSize" in data


# ═══════════════════════════════════════════════════════════════════════════════
#  Users endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestUsers:
    """CRUD /api/admin/users/*"""

    def test_list_users_empty(self, client):
        resp = client.get("/api/admin/users")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"] == []
        assert body["message"] == "success"
        assert body["code"] == 200

    def test_list_users_with_data(self, client, mock_db):
        mock_db.add_row(
            "users",
            username="alice",
            email="alice@x.com",
            password_hash="hashed",
            is_superuser=False,
            is_active=1,
            created_at="2024-01-01",
        )
        mock_db.add_row(
            "users",
            username="bob",
            email="bob@x.com",
            password_hash="hashed",
            is_superuser=True,
            is_active=1,
            created_at="2024-01-02",
        )

        resp = client.get("/api/admin/users")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["data"]) == 2
        usernames = [u["username"] for u in body["data"]]
        assert "alice" in usernames
        assert "bob" in usernames

    def test_update_user_success(self, client, mock_db):
        mock_db.add_row(
            "users",
            username="alice",
            email="alice@x.com",
            password_hash="hashed",
            is_superuser=False,
            is_active=1,
            created_at="2024-01-01",
        )

        resp = client.put("/api/admin/users/1", json={"is_active": False, "is_superuser": True})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"]["isActive"] is False
        assert body["data"]["isSuperuser"] is True

    def test_update_user_not_found(self, client):
        resp = client.put("/api/admin/users/999", json={"is_active": False})
        assert resp.status_code == 404

    def test_delete_user_success(self, client, mock_db):
        mock_db.add_row("users", username="alice", password_hash="hashed", is_superuser=False, is_active=1)
        resp = client.delete("/api/admin/users/1")
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "已删除"

    def test_delete_user_not_found(self, client):
        resp = client.delete("/api/admin/users/999")
        assert resp.status_code == 404

    def test_delete_user_self(self, client, mock_db):
        resp = client.delete("/api/admin/users/0")
        assert resp.status_code == 400

    def test_revoke_tokens_success(self, client, mock_db):
        mock_db.add_row("users", username="alice", password_hash="hashed", is_superuser=False, token_version=0)
        resp = client.post("/api/admin/users/1/revoke-tokens")
        assert resp.status_code == 200, resp.text
        assert resp.json()["ok"] is True
        user = mock_db._table("users")[1]
        assert user["token_version"] == 1

    def test_revoke_tokens_not_found(self, client):
        resp = client.post("/api/admin/users/999/revoke-tokens")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
#  Patents endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestPatents:
    """CRUD /api/admin/patents/*"""

    def test_list_patents_empty(self, client):
        resp = client.get("/api/admin/patents")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"] == []
        assert body["total"] == 0

    def test_list_patents_with_data(self, client, mock_db):
        mock_db.add_row(
            "patents",
            title="Patent Alpha",
            abstract="Abstract A",
            applicants=json.dumps(["Applicant A"]),
            inventors=json.dumps(["Inventor A"]),
            filing_date="2023-01-01",
            publication_date="2023-06-01",
            patent_number="US123",
            publication_number="WO123",
            ipc_codes=json.dumps(["G06F"]),
            claims="Claim 1",
            description="Description A",
            created_at="2024-01-01",
        )
        resp = client.get("/api/admin/patents")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["total"] == 1
        assert body["page"] == 1
        assert body["pageSize"] == 20
        patent = body["data"][0]
        assert patent["title"] == "Patent Alpha"
        assert patent["applicants"] == ["Applicant A"]

    def test_list_patents_pagination(self, client, mock_db):
        for i in range(5):
            mock_db.add_row(
                "patents",
                title=f"Patent {i}",
                abstract="",
                applicants=json.dumps([]),
                inventors=json.dumps([]),
                filing_date="",
                publication_date="",
                patent_number="",
                publication_number="",
                ipc_codes=json.dumps([]),
                claims="",
                description="",
                created_at=f"2024-01-0{i+1}",
            )
        resp = client.get("/api/admin/patents?page=1&page_size=2")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["total"] == 5
        assert body["page"] == 1
        assert body["pageSize"] == 2

    def test_list_patents_search(self, client, mock_db):
        mock_db.add_row(
            "patents",
            title="AI Chip Design",
            abstract="",
            applicants=json.dumps([]),
            inventors=json.dumps([]),
            filing_date="",
            publication_date="",
            patent_number="US456",
            publication_number="",
            ipc_codes=json.dumps([]),
            claims="",
            description="",
            created_at="2024-01-01",
        )
        mock_db.add_row(
            "patents",
            title="Another Patent",
            abstract="",
            applicants=json.dumps([]),
            inventors=json.dumps([]),
            filing_date="",
            publication_date="",
            patent_number="US789",
            publication_number="",
            ipc_codes=json.dumps([]),
            claims="",
            description="",
            created_at="2024-01-02",
        )
        resp = client.get("/api/admin/patents?q=Chip")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Search matches "AI Chip Design" (title LIKE '%Chip%') and also matches
        # via patent_number LIKE '%Chip%' for both patents — both have no "Chip" in patent_number,
        # so only "AI Chip Design" matches by title.  Result is 1 row.
        assert len(body["data"]) == 1
        assert body["data"][0]["title"] == "AI Chip Design"

    def test_create_patent_success(self, client, mock_db, monkeypatch):
        monkeypatch.setattr("app.api.admin.patent_db.PatentSearchEngine", MagicMock)

        payload = {
            "title": "New Invention",
            "abstract": "A novel invention",
            "applicants": ["Inventor Inc."],
            "inventors": ["John Doe"],
            "filing_date": "2024-01-15",
            "publication_date": "2024-07-15",
            "patent_number": "US2024001",
            "publication_number": "WO2024001",
            "ipc_codes": ["G06N"],
            "claims": "We claim this invention.",
            "description": "Full description here.",
        }
        resp = client.post("/api/admin/patents", json=payload)
        assert resp.status_code == 200, resp.text
        patent = resp.json()
        assert patent["title"] == "New Invention"
        assert patent["patentNumber"] == "US2024001"
        assert patent["applicants"] == ["Inventor Inc."]
        assert "id" in patent

    def test_create_patent_validation(self, client):
        resp = client.post("/api/admin/patents", json={"abstract": "no title"})
        assert resp.status_code == 422

    def test_update_patent_success(self, client, mock_db, monkeypatch):
        monkeypatch.setattr("app.api.admin.patent_db.PatentSearchEngine", MagicMock)
        mock_db.add_row(
            "patents",
            title="Original",
            abstract="Original abstract",
            applicants=json.dumps([]),
            inventors=json.dumps([]),
            filing_date="",
            publication_date="",
            patent_number="",
            publication_number="",
            ipc_codes=json.dumps([]),
            claims="",
            description="",
            created_at="2024-01-01",
        )
        resp = client.put("/api/admin/patents/1", json={"title": "Updated", "abstract": "Updated abstract"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["title"] == "Updated"
        assert resp.json()["abstract"] == "Updated abstract"

    def test_update_patent_not_found(self, client):
        resp = client.put("/api/admin/patents/999", json={"title": "Nope"})
        assert resp.status_code == 404

    def test_delete_patent_success(self, client, mock_db):
        mock_db.add_row(
            "patents",
            title="To Delete",
            abstract="",
            applicants=json.dumps([]),
            inventors=json.dumps([]),
            filing_date="",
            publication_date="",
            patent_number="",
            publication_number="",
            ipc_codes=json.dumps([]),
            claims="",
            description="",
            created_at="2024-01-01",
        )
        resp = client.delete("/api/admin/patents/1")
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "删除成功"
        assert 1 not in mock_db._table("patents")

    def test_delete_patent_not_found(self, client):
        resp = client.delete("/api/admin/patents/999")
        assert resp.status_code == 404

    def test_import_patents_success(self, client, mock_db, monkeypatch):
        monkeypatch.setattr("app.api.admin.patent_db.PatentSearchEngine", MagicMock)
        payload = [
            {
                "title": "Patent 1",
                "abstract": "Abstract 1",
                "applicants": ["Company A"],
                "inventors": ["Alice"],
                "filing_date": "",
                "publication_date": "",
                "patent_number": "",
                "publication_number": "",
                "ipc_codes": [],
                "claims": "",
                "description": "",
            },
            {
                "title": "Patent 2",
                "abstract": "Abstract 2",
                "applicants": ["Company B"],
                "inventors": ["Bob"],
                "filing_date": "",
                "publication_date": "",
                "patent_number": "",
                "publication_number": "",
                "ipc_codes": [],
                "claims": "",
                "description": "",
            },
        ]
        resp = client.post("/api/admin/patents/import", json=payload)
        assert resp.status_code == 200, resp.text
        assert resp.json()["count"] == 2
        assert "成功导入" in resp.json()["message"]

    def test_import_patents_bad_format(self, client):
        resp = client.post("/api/admin/patents/import", json={"title": "not a list"})
        assert resp.status_code == 422

    def test_upload_patent_pdf(self, client, mock_db, monkeypatch):
        monkeypatch.setattr("app.api.admin.patent_db.PatentSearchEngine", MagicMock)

        # Patch file_storage.enabled property
        import app.services.file_storage_service as fss

        p = PropertyMock(return_value=False)
        monkeypatch.setattr(type(fss.file_storage), "enabled", p)

        # Mock parse_file (imported inside the function body from app.algorithm.file_parser)
        monkeypatch.setattr(
            "app.algorithm.file_parser.parse_file",
            lambda path, **kw: {"content": "Patent abstract: AI chip. Claim 1: A method.", "type": "pdfminer"},
        )

        # Mock extract_patent_fields (imported inside the function body)
        monkeypatch.setattr(
            "app.algorithm.patent_extractor.extract_patent_fields",
            lambda text: {
                "title": "AI Chip Patent",
                "abstract": "An AI chip design.",
                "applicants": ["Chip Corp"],
                "inventors": ["Dr. Smith"],
                "filing_date": "2024-03-01",
                "publication_date": "2024-09-01",
                "patent_number": "US2024002",
                "publication_number": "WO2024002",
                "ipc_codes": ["G06N", "H01L"],
                "claims": "Claim 1: A novel AI chip.",
                "description": "Full description of AI chip.",
            },
        )

        # Mock model_resolver (imported inside the function body from app.algorithm.model_resolver)
        mock_resolver = MagicMock()
        mock_resolver.get_assigned_settings.return_value = {}
        monkeypatch.setattr("app.algorithm.model_resolver.model_resolver", mock_resolver)

        fake_pdf = b"%PDF-1.4 fake pdf content"
        resp = client.post(
            "/api/admin/patents/upload",
            files={"file": ("test.pdf", fake_pdf, "application/pdf")},
            data={"mode": "pdfminer"},
        )
        assert resp.status_code == 200, resp.text
        patent = resp.json()
        assert patent["title"] == "AI Chip Patent"
        assert patent["patentNumber"] == "US2024002"
        assert patent["mode"] == "pdfminer"
        assert "id" in patent

    def test_upload_patent_pdf_wrong_extension(self, client):
        resp = client.post(
            "/api/admin/patents/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            data={"mode": "pdfminer"},
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
#  Settings endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettings:
    """GET/PUT /api/admin/settings/*"""

    def test_get_assigned_models(self, client, mock_db):
        mock_db.add_row("system_settings", key="chat_model", value="silicon::deepseek-chat")
        mock_db.add_row("system_settings", key="embedding_model", value="silicon::bge-large")

        resp = client.get("/api/admin/settings/models/assigned")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["chat_model"] == "silicon::deepseek-chat"
        assert data["embedding_model"] == "silicon::bge-large"
        assert data["rerank_model"] is None
        assert data["ocr_model"] is None
        assert data["extract_model"] is None

    def test_set_assigned_models(self, client, mock_db):
        resp = client.put(
            "/api/admin/settings/models/assigned",
            json={"chat_model": "openai::gpt-4o", "embedding_model": "openai::text-embedding-3-small"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "saved"

        table = mock_db._table("system_settings")
        by_key = {r["key"]: r["value"] for r in table.values()}
        assert by_key["chat_model"] == "openai::gpt-4o"
        assert by_key["embedding_model"] == "openai::text-embedding-3-small"

    def test_get_rag_config(self, client, mock_db):
        mock_db.add_row("system_settings", key="chunk_size", value="512")
        mock_db.add_row("system_settings", key="search_mode", value="hybrid")

        resp = client.get("/api/admin/settings/rag")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["chunk_size"] == "512"
        assert data["search_mode"] == "hybrid"
        assert data["chunk_overlap"] is None

    def test_set_rag_config(self, client, mock_db):
        resp = client.put(
            "/api/admin/settings/rag",
            json={"chunk_size": 256, "chunk_overlap": 32, "search_mode": "hybrid"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "saved"

        table = mock_db._table("system_settings")
        by_key = {r["key"]: r["value"] for r in table.values()}
        assert by_key["chunk_size"] == "256"
        assert by_key["chunk_overlap"] == "32"
        assert by_key["search_mode"] == "hybrid"

    def test_get_available_models(self, client, monkeypatch):
        """Returns models grouped by capability (mock model_service + registry)."""
        # Mock model_service.list_all (already patched in client fixture to MagicMock)
        client._mock_svc.list_all.return_value = [
            {
                "providerId": "silicon",
                "name": "SiliconFlow",
                "isEnabled": True,
                "models": [
                    {"id": "deepseek-chat", "capabilities": ["chat"]},
                    {"id": "bge-large", "capabilities": ["embedding"]},
                    {"id": "bge-reranker", "capabilities": ["rerank"]},
                ],
            },
            {
                "providerId": "openai",
                "name": "OpenAI",
                "isEnabled": True,
                "models": [
                    {"id": "gpt-4o", "capabilities": ["chat", "vision"]},
                    {"id": "text-embedding-3", "capabilities": ["embedding"]},
                ],
            },
            {
                "providerId": "disabled",
                "name": "Disabled",
                "isEnabled": False,
                "models": [{"id": "old-model", "capabilities": ["chat"]}],
            },
        ]

        # The settings endpoint imports from providers_registry inside the function body.
        # Patch the original source module so function-body imports see the mocks.
        monkeypatch.setattr(
            "app.algorithm.providers_registry.get_model_capabilities",
            lambda m: m.get("capabilities", ["chat"]),
        )
        monkeypatch.setattr(
            "app.algorithm.providers_registry.get_model_id",
            lambda m: m.get("id", ""),
        )
        monkeypatch.setattr("app.algorithm.providers_registry.CAPABILITY_EMBEDDING", "embedding")
        monkeypatch.setattr("app.algorithm.providers_registry.CAPABILITY_RERANK", "rerank")
        monkeypatch.setattr("app.algorithm.providers_registry.CAPABILITY_VISION", "vision")

        resp = client.get("/api/admin/settings/models/available")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "chat" in data
        assert "embedding" in data
        assert "rerank" in data
        assert "vision" in data
        assert "extract" in data

        chat_ids = {m["modelId"] for m in data["chat"]}
        assert "deepseek-chat" in chat_ids
        assert "gpt-4o" in chat_ids
        assert "old-model" not in chat_ids  # disabled provider excluded

        embedding_ids = {m["modelId"] for m in data["embedding"]}
        assert "bge-large" in embedding_ids
        assert "text-embedding-3" in embedding_ids


# ═══════════════════════════════════════════════════════════════════════════════
#  Providers endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviders:
    """CRUD /api/admin/providers/*"""

    # ── builtin & list ───────────────────────────────────────────────────

    def test_list_builtin(self, client):
        fake_builtin = [
            {"providerId": "silicon", "name": "SiliconFlow", "isConfigured": False},
            {"providerId": "openai", "name": "OpenAI", "isConfigured": True},
        ]
        client._mock_svc.list_builtin.return_value = fake_builtin

        resp = client.get("/api/admin/providers/builtin")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == fake_builtin

    def test_list_providers(self, client):
        fake_providers = [
            {"providerId": "silicon", "name": "SiliconFlow", "models": []},
            {"providerId": "openai", "name": "OpenAI", "models": []},
        ]
        client._mock_svc.list_all.return_value = fake_providers

        resp = client.get("/api/admin/providers")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == fake_providers

    # ── CRUD ─────────────────────────────────────────────────────────────

    def test_add_provider_success(self, client):
        client._mock_svc.get.return_value = None
        fake_result = {"providerId": "my-provider", "name": "My Provider", "isEnabled": True}
        client._mock_svc.add.return_value = fake_result

        payload = {
            "provider_id": "my-provider",
            "name": "My Provider",
            "api_host": "https://api.myprovider.com",
            "protocol": "openai",
        }
        resp = client.post("/api/admin/providers", json=payload)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["providerId"] == "my-provider"
        assert resp.json()["message"] == "供应商已添加"

    def test_add_provider_duplicate(self, client):
        client._mock_svc.get.return_value = {"providerId": "existing"}

        payload = {
            "provider_id": "existing",
            "name": "Existing",
            "api_host": "https://api.example.com",
        }
        resp = client.post("/api/admin/providers", json=payload)
        assert resp.status_code == 400

    def test_update_provider_success(self, client):
        client._mock_svc.update.return_value = {"providerId": "silicon", "name": "Updated Silicon"}

        resp = client.put("/api/admin/providers/silicon", json={"name": "Updated Silicon"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "Updated Silicon"
        assert resp.json()["message"] == "更新成功"

    def test_update_provider_not_found(self, client):
        client._mock_svc.update.return_value = None

        resp = client.put("/api/admin/providers/nonexistent", json={"name": "Nope"})
        assert resp.status_code == 404

    def test_delete_provider_success(self, client):
        client._mock_svc.delete.return_value = True

        resp = client.delete("/api/admin/providers/silicon")
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "删除成功"

    # ── toggle ───────────────────────────────────────────────────────────

    def test_toggle_provider(self, client):
        client._mock_svc.toggle.return_value = {"providerId": "silicon", "isEnabled": False}

        resp = client.put("/api/admin/providers/silicon/toggle")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["isEnabled"] is False
        assert resp.json()["message"] == "状态已切换"

    def test_toggle_provider_not_found(self, client):
        client._mock_svc.toggle.return_value = None

        resp = client.put("/api/admin/providers/nonexistent/toggle")
        assert resp.status_code == 404

    # ── connection & detection ───────────────────────────────────────────

    def test_check_connection(self, client):
        client._mock_svc.check_connection = AsyncMock(return_value={"status": "ok", "latency": 123})

        resp = client.post("/api/admin/providers/silicon/check")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "ok"

    def test_check_connection_with_model(self, client):
        client._mock_svc.check_connection = AsyncMock(return_value={"status": "ok", "latency": 50})

        resp = client.post("/api/admin/providers/silicon/check", json={"model": "gpt-4"})
        assert resp.status_code == 200, resp.text

    def test_detect_models(self, client):
        client._mock_svc.detect_models = AsyncMock(
            return_value={"models": [{"id": "model-a"}, {"id": "model-b"}]}
        )

        resp = client.post("/api/admin/providers/silicon/detect-models")
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["data"]["models"]) == 2

    # ── reconcile ────────────────────────────────────────────────────────

    def test_reconcile_models(self, client):
        client._mock_svc.detect_models = AsyncMock(
            return_value={
                "models": [{"id": "new-model"}, {"id": "existing-model"}, {"id": "another-new"}],
            }
        )
        client._mock_svc.reconcile_models.return_value = {
            "added": [{"id": "new-model"}, {"id": "another-new"}],
            "removed": [{"id": "old-model"}],
            "unchanged": [{"id": "existing-model"}],
        }

        resp = client.post("/api/admin/providers/silicon/models/reconcile")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data["added"]) == 2
        assert len(data["removed"]) == 1
        assert len(data["unchanged"]) == 1

    def test_reconcile_models_not_found(self, client):
        client._mock_svc.detect_models = AsyncMock(return_value={"models": []})
        client._mock_svc.reconcile_models.return_value = None

        resp = client.post("/api/admin/providers/nonexistent/models/reconcile")
        assert resp.status_code == 404

    def test_reconcile_apply(self, client):
        client._mock_svc.reconcile_apply.return_value = {
            "providerId": "silicon",
            "models": [{"id": "new-model"}, {"id": "existing-model"}],
        }

        resp = client.post(
            "/api/admin/providers/silicon/models/reconcile-apply",
            json={"to_add": ["new-model"], "to_remove": ["old-model"]},
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["data"]["models"]) == 2

    def test_reconcile_apply_not_found(self, client):
        client._mock_svc.reconcile_apply.return_value = None

        resp = client.post(
            "/api/admin/providers/nonexistent/models/reconcile-apply",
            json={"to_add": [], "to_remove": []},
        )
        assert resp.status_code == 404

    # ── model CRUD ───────────────────────────────────────────────────────

    def test_batch_check_models(self, client):
        client._mock_svc.batch_check_models = AsyncMock(
            return_value={
                "providerId": "silicon",
                "models": [
                    {"modelId": "model-a", "status": "ok", "latency": 100},
                    {"modelId": "model-b", "status": "error", "error": "timeout"},
                ],
            }
        )

        resp = client.post(
            "/api/admin/providers/silicon/models/check",
            json={"models": ["model-a", "model-b"]},
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["data"]["models"]) == 2

    def test_list_provider_models(self, client, mock_db):
        mock_db.add_row(
            "model_providers",
            provider_id="silicon",
            name="SiliconFlow",
            protocol="openai",
            api_host="https://api.siliconflow.cn",
            models=json.dumps([]),
            is_enabled=1,
            max_rpm=60,
            current_rpm=0,
            request_count=0,
            last_used_at="",
            created_at="2024-01-01",
        )
        # Mock ModelsCrudService (imported lazily inside the endpoint function)
        import app.algorithm.models_crud as models_crud_mod

        crud_mock = MagicMock()
        crud_mock.list_by_provider.return_value = [
            {"modelId": "deepseek-chat", "capabilities": ["chat"]},
            {"modelId": "bge-large", "capabilities": ["embedding"]},
        ]
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(models_crud_mod, "ModelsCrudService", lambda: crud_mock)

        resp = client.get("/api/admin/providers/silicon/models")
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["data"]) == 2

    def test_update_provider_model(self, client, monkeypatch):
        import app.algorithm.models_crud as models_crud_mod

        crud_mock = MagicMock()
        crud_mock.update.return_value = {
            "modelId": "gpt-4o",
            "name": "GPT-4 Optimized",
            "capabilities": ["chat"],
        }
        monkeypatch.setattr(models_crud_mod, "ModelsCrudService", lambda: crud_mock)

        resp = client.put(
            "/api/admin/providers/openai/models/gpt-4o",
            json={"name": "GPT-4 Optimized"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "GPT-4 Optimized"

    def test_update_provider_model_not_found(self, client, monkeypatch):
        import app.algorithm.models_crud as models_crud_mod

        crud_mock = MagicMock()
        crud_mock.update.return_value = None
        monkeypatch.setattr(models_crud_mod, "ModelsCrudService", lambda: crud_mock)

        resp = client.put(
            "/api/admin/providers/openai/models/nonexistent",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    def test_delete_provider_model(self, client, mock_db, monkeypatch):
        import app.algorithm.models_crud as models_crud_mod

        crud_mock = MagicMock()
        monkeypatch.setattr(models_crud_mod, "ModelsCrudService", lambda: crud_mock)

        mock_db.add_row(
            "model_providers",
            provider_id="silicon",
            name="SiliconFlow",
            protocol="openai",
            api_host="https://api.siliconflow.cn",
            models=json.dumps([{"id": "deepseek-chat"}, {"id": "bge-large"}]),
            is_enabled=1,
            max_rpm=60,
            current_rpm=0,
            request_count=0,
            last_used_at="",
            created_at="2024-01-01",
        )

        resp = client.request(
            "DELETE",
            "/api/admin/providers/silicon/models/deepseek-chat",
            json={},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "模型已删除"
