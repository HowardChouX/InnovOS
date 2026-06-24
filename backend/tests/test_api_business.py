"""
Business API tests — Tasks, Analysis, Workflow, Solutions, Evaluation, Feedback.

Uses a generic in-memory mock database to test all business routes
without requiring PostgreSQL.
"""

import json
import re

import pytest
from fastapi.testclient import TestClient


# ── Mock Row ──


class MockRow(dict):
    """Dict row that supports both string and integer indexing (mimics _Row)."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


# ── Generic In-Memory MockDB ──


class MockDB:
    """In-memory mock database supporting multiple tables.

    Mimics the _PostgresDatabase API (execute, fetchone, fetchall, commit, close).
    Handles the SQL subset used by the business API routes:
      - SELECT … FROM table WHERE … ORDER BY … LIMIT … OFFSET …
      - INSERT INTO table (cols) VALUES (?, …) RETURNING col
      - UPDATE table SET col=?, … WHERE …
      - DELETE FROM table WHERE …
      - Special: SELECT … WHERE id = last_insert_rowid()
    """

    def __init__(self):
        self._tables: dict[str, dict[int, dict]] = {}  # name → {id → row}
        self._ids: dict[str, int] = {}  # name → next_id
        self._last_result: list[MockRow] = []
        self._last_insert_id: int | None = None

    # Table-specific default columns (mimics PostgreSQL column defaults)
    _TABLE_DEFAULTS: dict[str, dict] = {
        "tasks": {
            "status": "pending",
        },
        "solutions": {
            "rating": 0,
            "principles": "[]",
            "patent_references": "[]",
        },
        "evaluations": {
            "status": "completed",
            "details": "{}",
            "root_cause_cut": 0,
            "original_contradiction_resolved": 0,
            "new_contradictions": "[]",
            "function_deficits_filled": "[]",
            "new_harmful_interactions": "[]",
            "ifr_distance": 0,
            "ifr_gap_description": "",
            "ifr_parameters_achieved": "[]",
            "overall_verdict": "",
            "evolution_alignment": "",
            "aligned_laws": "[]",
            "misaligned_laws": "[]",
            "maturity": "",
            "confidence": 0,
        },
        "feedbacks": {
            "feedback_type": "general",
            "comments": "",
        },
        "workflows": {
            "steps": "[]",
        },
    }

    # ── helpers ──

    def _ensure_table(self, name: str) -> dict[int, dict]:
        name = name.lower()
        if name not in self._tables:
            self._tables[name] = {}
            self._ids[name] = 1
        return self._tables[name]

    def _next_id(self, table: str) -> int:
        key = table.lower()
        n = self._ids.get(key, 1)
        self._ids[key] = n + 1
        return n

    _TABLE_RE = re.compile(
        r'(?:DELETE\s+FROM|INTO|UPDATE|FROM)\s+(\w+)', re.IGNORECASE
    )
    _JOIN_TABLE_RE = re.compile(
        r'FROM\s+(\w+)\s+\w+\s+JOIN\s+(\w+)\s+\w+\s+ON\s+\w+\.(\w+)\s*=\s*\w+\.(\w+)', re.IGNORECASE
    )

    def _parse_table(self, sql: str) -> str | None:
        if " JOIN " in sql.upper():
            return self._parse_table_join(sql)
        m = self._TABLE_RE.search(sql)
        return m.group(1).lower() if m else None

    def _parse_table_join(self, sql: str) -> str | None:
        m = self._JOIN_TABLE_RE.search(sql)
        if m:
            return m.group(1).lower()
        return None

    def _extract_where_text(self, sql: str) -> tuple[str, str]:
        """Return (where_clause_text, trailing_clause)."""
        parts = sql.split("WHERE")
        if len(parts) < 2:
            return "", ""
        text = parts[1].strip()
        trail = ""
        for kw in ("ORDER BY", "LIMIT", "OFFSET"):
            idx = text.upper().find(kw.upper())
            if idx >= 0:
                trail = text[idx:] + " " + trail
                text = text[:idx].strip()
        return text, trail.strip()

    def _parse_in_conditions(self, text: str, params: list, idx: int):
        """Replace IN(?,?,?) placeholders; return (conditions, remaining_text, new_idx)."""
        conditions: list[tuple] = []
        # Work on a copy and remove IN matches
        rest = text
        for m in re.finditer(r"(\w+)\s+IN\s*\(([^)]+)\)", text, re.IGNORECASE):
            col = m.group(1)
            cnt = m.group(2).count("?")
            vals = tuple(params[idx : idx + cnt])
            idx += cnt
            conditions.append(("IN", col, vals))
            rest = rest.replace(m.group(0), "", 1)
        return conditions, rest, idx

    def _parse_conditions(
        self, sql: str, params: tuple | list
    ) -> list[tuple]:
        """Return list of (op, column, value) from WHERE clause."""
        where_text, _ = self._extract_where_text(sql)
        if not where_text or not params:
            return []

        p = list(params)
        idx = 0
        conditions: list[tuple] = []

        # IN clauses first
        in_conds, rest, idx = self._parse_in_conditions(where_text, p, idx)
        conditions.extend(in_conds)

        rest = rest.replace("= ?", "=?").replace("LIKE ?", "LIKE?")
        for clause in rest.split("AND"):
            clause = clause.strip()
            if not clause:
                continue
            if "=?" in clause:
                col = clause.split("=")[0].strip()
                val = p[idx] if idx < len(p) else None
                idx += 1
                conditions.append(("EQ", col, val))
            elif "LIKE?" in clause:
                col = clause.split("LIKE")[0].strip()
                val = p[idx] if idx < len(p) else None
                idx += 1
                conditions.append(("LIKE", col, val))
        return conditions

    def _row_matches(self, row: dict, conditions: list[tuple]) -> bool:
        for op, col, val in conditions:
            col = col.split(".")[-1]  # strip table alias: t.user_id → user_id
            rv = row.get(col)
            if op == "EQ":
                if rv is None or str(rv) != str(val):
                    return False
            elif op == "LIKE":
                pat = str(val).replace("%", "").lower() if val else ""
                if pat not in str(rv or "").lower():
                    return False
            elif op == "IN":
                if rv is None or rv not in val:
                    return False
        return True

    def _parse_insert_cols(self, sql: str) -> list[str]:
        m = re.search(r"\(([^)]+)\)\s*VALUES", sql)
        if m:
            return [c.strip() for c in m.group(1).split(",") if c.strip()]
        return []

    def _parse_order_limit(self, sql: str):
        """Return (order_col, desc, limit, offset)."""
        oc = None
        desc = False
        limit = None
        offset = None
        m = re.search(r"ORDER BY\s+(\w+)\s*(DESC)?", sql, re.IGNORECASE)
        if m:
            oc = m.group(1)
            desc = m.group(2) is not None and "DESC" in m.group(2).upper()
        m = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
        if m:
            limit = int(m.group(1))
        m = re.search(r"OFFSET\s+(\d+)", sql, re.IGNORECASE)
        if m:
            offset = int(m.group(1))
        return oc, desc, limit, offset

    def _handle_update(self, sql: str, params: tuple | list):
        table = self._parse_table(sql)
        if not table:
            return
        tbl = self._ensure_table(table)

        # Split SET / WHERE
        after_set = sql.split("SET", 1)[1] if "SET" in sql else ""
        where_text = ""
        set_text = after_set
        if "WHERE" in after_set.upper():
            parts = after_set.split("WHERE")
            set_text = parts[0]
            where_text = parts[1]

        # Extract SET columns that consume ? params
        set_matches = re.findall(r"(\w+)\s*=\s*\?", set_text)
        set_cols = [m for m in set_matches]

        p = list(params)
        set_params = p[: len(set_cols)]
        where_params = p[len(set_cols) :]

        # Re-parse WHERE using a synthetic SELECT so _parse_conditions
        # correctly splits params between conditions.
        conditions: list[tuple] = []
        if where_text.strip():
            wt = where_text.strip()
            for kw in ("ORDER BY", "LIMIT", "OFFSET"):
                idx = wt.upper().find(kw.upper())
                if idx >= 0:
                    wt = wt[:idx]
            synth_sql = f"SELECT 1 FROM {table} WHERE {wt}"
            conditions = self._parse_conditions(synth_sql, tuple(where_params))

        # Apply updates
        for row in tbl.values():
            if self._row_matches(row, conditions):
                for i, col in enumerate(set_cols):
                    if i < len(set_params):
                        row[col] = set_params[i]

    # ── public API ──

    def execute(self, sql: str, params: tuple | list | None = None):
        self._last_result = []
        params = params or ()

        # Special: last_insert_rowid()
        if "last_insert_rowid()" in sql:
            if self._last_insert_id is not None:
                tbl = self._ensure_table(self._parse_table(sql) or "")
                row = tbl.get(self._last_insert_id)  # type: ignore[return-value]
                if row:
                    self._last_result = [MockRow(row.copy())]
            return self

        upper = sql.strip().upper()
        table = self._parse_table(sql)

        # ── SELECT ──
        if upper.startswith("SELECT"):
            if not table:
                return self
            tbl = self._ensure_table(table)
            is_count = "COUNT(*)" in upper
            conditions = self._parse_conditions(sql, params)

            matching = list(tbl.values())
            for cond in conditions:
                matching = [r for r in matching if self._row_matches(r, [cond])]

            oc, desc, limit, offset = self._parse_order_limit(sql)
            if oc and matching:
                matching = sorted(
                    matching, key=lambda r: str(r.get(oc, "") or ""), reverse=desc
                )
            if offset is not None:
                matching = matching[offset:]
            if limit is not None:
                matching = matching[:limit]

            if is_count:
                self._last_result = [MockRow({0: len(matching)})]
            else:
                self._last_result = [MockRow(r.copy()) for r in matching]

        # ── INSERT ──
        elif upper.startswith("INSERT"):
            if not table:
                return self
            tbl = self._ensure_table(table)
            cols = self._parse_insert_cols(sql)
            rid = self._next_id(table)
            now = "2024-01-01 00:00:00"
            row: dict = {"id": rid}
            p = list(params)
            for i, col in enumerate(cols):
                row[col] = p[i] if i < len(p) else None
            row.setdefault("created_at", now)
            row.setdefault("updated_at", now)
            # Apply table-specific defaults
            for col, val in self._TABLE_DEFAULTS.get(table, {}).items():
                row.setdefault(col, val)
            tbl[rid] = row
            self._last_insert_id = rid

            ret_m = re.search(r"RETURNING\s+(\*|\w+(?:,\s*\w+)*)", sql, re.IGNORECASE)
            if ret_m:
                ret_cols = ret_m.group(1).strip()
                if ret_cols == "*":
                    self._last_result = [MockRow(row.copy())]
                else:
                    self._last_result = [MockRow({c.strip(): row.get(c.strip()) for c in ret_cols.split(",")})]
            else:
                self._last_result = []

        # ── UPDATE ──
        elif upper.startswith("UPDATE"):
            self._handle_update(sql, params)

        # ── DELETE ──
        elif upper.startswith("DELETE"):
            if not table:
                return self
            tbl = self._ensure_table(table)
            conditions = self._parse_conditions(sql, params)
            to_del = []
            for rid, row in tbl.items():
                if self._row_matches(row, conditions):
                    to_del.append(rid)
            for rid in to_del:
                del tbl[rid]

        return self

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


# ── Fixtures ──


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def client(mock_db, monkeypatch):
    """FastAPI TestClient with all business routers and mock DB injection.

    Monkeypatches both the module-level ``get_db`` in ``app.database`` AND
    the local ``get_db`` references already captured by each router module
    (imported earlier via ``from app.database import get_db``).
    """
    # Override the module-level attribute
    monkeypatch.setattr("app.database.get_db", lambda: mock_db)

    # Also override the local reference in every module that has already
    # done ``from app.database import get_db`` at import time.
    _GET_DB_MODULES = [
        "app.api.tasks",
        "app.api.analysis",
        "app.api.workflow",
        "app.api.solutions",
        "app.api.evaluation",
        "app.api.feedback",
        "app.auth",
        "app.algorithm.evaluation_service",
    ]
    for mod in _GET_DB_MODULES:
        try:
            monkeypatch.setattr(f"{mod}.get_db", lambda: mock_db)
        except AttributeError:
            pass  # module may not be imported yet — fine

    from fastapi import FastAPI
    from app.auth import get_current_user
    from app.api.tasks import router as tasks_router
    from app.api.analysis import router as analysis_router
    from app.api.workflow import router as workflow_router
    from app.api.solutions import router as solutions_router
    from app.api.evaluation import router as evaluation_router
    from app.api.feedback import router as feedback_router

    test_app = FastAPI()
    test_app.include_router(tasks_router)
    test_app.include_router(analysis_router)
    test_app.include_router(workflow_router)
    test_app.include_router(solutions_router)
    test_app.include_router(evaluation_router)
    test_app.include_router(feedback_router)
    test_app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "user_id": 1,
        "username": "testuser",
        "role": "user",
        "email": "",
        "created_at": "",
    }

    return TestClient(test_app)


# ── Seed helpers ──


def _seed_task(
    mock_db,
    task_id: int = 1,
    user_id: int = 1,
    title: str = "Test Task",
    description: str = "Test Description",
    tags: str = "[]",
    status: str = "pending",
) -> int:
    tbl = mock_db._ensure_table("tasks")
    now = "2024-01-01 00:00:00"
    tbl[task_id] = {
        "id": task_id,
        "user_id": user_id,
        "title": title,
        "description": description,
        "tags": tags,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if mock_db._ids.get("tasks", 0) <= task_id:
        mock_db._ids["tasks"] = task_id + 1
    return task_id


def _seed_analysis(mock_db, task_id: int = 1):
    tbl = mock_db._ensure_table("analyses")
    tbl[task_id] = {
        "id": task_id,
        "task_id": task_id,
        "center_node": json.dumps({"id": "c1", "description": "核心目标"}),
        "satellite_nodes": json.dumps(
            [{"id": "s1", "label": "性能", "description": "提升性能"}]
        ),
        "edges": json.dumps([{"from": "c1", "to": "s1"}]),
        "principles": json.dumps(["分割原理", "动态化原理"]),
    }
    if mock_db._ids.get("analyses", 0) <= task_id:
        mock_db._ids["analyses"] = task_id + 1


def _seed_workflow(
    mock_db,
    task_id: int = 1,
    status: str = "idle",
    steps: list | None = None,
):
    tbl = mock_db._ensure_table("workflows")
    if steps is None:
        steps = []
    tbl[task_id] = {
        "id": task_id,
        "task_id": task_id,
        "status": status,
        "steps": json.dumps(steps),
        "created_at": "2024-01-01 00:00:00",
    }
    if mock_db._ids.get("workflows", 0) <= task_id:
        mock_db._ids["workflows"] = task_id + 1


def _seed_solution(
    mock_db,
    solution_id: int = 1,
    task_id: int = 1,
    user_id: int = 1,
    title: str = "Solution A",
    description: str = "Description A",
    rating: int = 0,
):
    tbl = mock_db._ensure_table("solutions")
    now = "2024-01-01 00:00:00"
    tbl[solution_id] = {
        "id": solution_id,
        "task_id": task_id,
        "user_id": user_id,
        "title": title,
        "description": description,
        "principles": json.dumps(["原理A"]),
        "confidence_score": 85,
        "patent_references": json.dumps([]),
        "rating": rating,
        "created_at": now,
    }
    if mock_db._ids.get("solutions", 0) <= solution_id:
        mock_db._ids["solutions"] = solution_id + 1
    # Ensure a matching tasks row exists for JOIN-based user_id checks
    task_tbl = mock_db._ensure_table("tasks")
    if task_id not in task_tbl:
        _seed_task(mock_db, task_id=task_id, user_id=user_id)
        mock_db._ids["tasks"] = max(mock_db._ids.get("tasks", 0), task_id + 1)
    return solution_id


def _seed_evaluation(
    mock_db,
    evaluation_id: int = 1,
    solution_id: int = 1,
    user_id: int = 1,
    dimension: str = "innovation",
    score: float = 85.0,
):
    tbl = mock_db._ensure_table("evaluations")
    now = "2024-01-01 00:00:00"
    tbl[evaluation_id] = {
        "id": evaluation_id,
        "solution_id": solution_id,
        "user_id": user_id,
        "dimension": dimension,
        "score": score,
        "details": json.dumps({"strengths": ["创新性强"], "weaknesses": []}),
        "status": "completed",
        "created_at": now,
        "root_cause_cut": 1,
        "original_contradiction_resolved": 1,
        "new_contradictions": json.dumps([]),
        "function_deficits_filled": json.dumps([]),
        "new_harmful_interactions": json.dumps([]),
        "ifr_distance": 3.5,
        "ifr_gap_description": "需进一步优化",
        "ifr_parameters_achieved": json.dumps(["参数A"]),
        "overall_verdict": "方案可行",
        "evolution_alignment": "aligned",
        "aligned_laws": json.dumps(["S曲线"]),
        "misaligned_laws": json.dumps([]),
        "maturity": "成熟期",
        "confidence": 0.85,
    }
    if mock_db._ids.get("evaluations", 0) <= evaluation_id:
        mock_db._ids["evaluations"] = evaluation_id + 1


# ── Test Classes ──


class TestTasks:
    """Tasks CRUD 接口测试"""

    # ── GET /api/tasks ──

    def test_list_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0
        assert data["code"] == 200

    def test_list_with_data(self, client, mock_db):
        _seed_task(mock_db, 1, title="Task 1")
        _seed_task(mock_db, 2, title="Task 2")
        resp = client.get("/api/tasks")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 2
        titles = [d["title"] for d in data["data"]]
        assert "Task 1" in titles
        assert "Task 2" in titles

    def test_list_respects_user_scoping(self, client, mock_db):
        """Other user's tasks are not visible."""
        _seed_task(mock_db, 1, user_id=1, title="Mine")
        _seed_task(mock_db, 2, user_id=2, title="Not mine")
        resp = client.get("/api/tasks")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "Mine"

    # ── POST /api/tasks ──

    def test_create_success(self, client, mock_db):
        resp = client.post(
            "/api/tasks",
            json={"title": "New Task", "description": "New Desc", "tags": ["tag1"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["title"] == "New Task"
        assert data["data"]["description"] == "New Desc"
        assert data["data"]["tags"] == ["tag1"]
        assert data["data"]["id"] is not None

    def test_create_missing_title_validation(self, client):
        """Pydantic rejects missing title field."""
        resp = client.post(
            "/api/tasks",
            json={"description": "Some desc"},
        )
        assert resp.status_code == 422, resp.text

    def test_create_missing_description_validation(self, client):
        """Pydantic rejects missing description field."""
        resp = client.post(
            "/api/tasks",
            json={"title": "Title"},
        )
        assert resp.status_code == 422, resp.text

    # ── GET /api/tasks/{task_id} ──

    def test_get_by_id_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.get("/api/tasks/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["id"] == "1"
        assert data["data"]["title"] == "Test Task"

    def test_get_by_id_not_found(self, client):
        resp = client.get("/api/tasks/999")
        assert resp.status_code == 404, resp.text

    # ── PUT /api/tasks/{task_id} ──

    def test_update_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.put(
            "/api/tasks/1",
            json={"title": "Updated", "description": "Updated desc"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["title"] == "Updated"
        assert data["data"]["description"] == "Updated desc"

    def test_update_invalid_status(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.put("/api/tasks/1", json={"status": "invalid_status"})
        assert resp.status_code == 400, resp.text
        assert "Invalid status" in resp.json()["detail"]

    def test_update_not_found(self, client):
        resp = client.put(
            "/api/tasks/999",
            json={"title": "Nope"},
        )
        assert resp.status_code == 404, resp.text

    # ── DELETE /api/tasks/{task_id} ──

    def test_delete_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_solution(mock_db, 1, task_id=1)
        _seed_evaluation(mock_db, 1, solution_id=1)
        resp = client.delete("/api/tasks/1")
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "deleted"
        # Verify the task is gone
        get_resp = client.get("/api/tasks/1")
        assert get_resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/tasks/999")
        assert resp.status_code == 404, resp.text


class TestAnalysis:
    """Analysis 接口测试"""

    # ── GET /api/analysis/{task_id} ──

    def test_get_analysis_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_analysis(mock_db, 1)
        resp = client.get("/api/analysis/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["taskId"] == "1"
        assert data["centerNode"]["description"] == "核心目标"
        assert len(data["satelliteNodes"]) == 1

    def test_get_analysis_task_not_found(self, client):
        resp = client.get("/api/analysis/999")
        assert resp.status_code == 404, resp.text

    def test_get_analysis_not_yet_generated(self, client, mock_db):
        _seed_task(mock_db, 1)
        # No analysis seeded → 404
        resp = client.get("/api/analysis/1")
        assert resp.status_code == 404, resp.text
        assert "Analysis not yet generated" in resp.json()["detail"]

    # ── POST /api/analysis/{task_id}/trigger ──

    def test_trigger_analysis_success(self, client, mock_db):
        _seed_task(mock_db, 1, description="Test the analysis trigger")
        resp = client.post("/api/analysis/1/trigger")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "analyzing"

    def test_trigger_analysis_task_not_found(self, client):
        resp = client.post("/api/analysis/999/trigger")
        assert resp.status_code == 404, resp.text

    def test_trigger_analysis_already_exists(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_analysis(mock_db, 1)
        resp = client.post("/api/analysis/1/trigger")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["message"] == "已有分析结果"

    # ── POST /api/analysis/{task_id}/proceed ──

    def test_proceed_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_workflow(
            mock_db,
            1,
            status="awaiting_rating",
            steps=[
                {
                    "agent_id": "agent1",
                    "agent_type": "problem_analysis",
                    "status": "completed",
                    "output": json.dumps({"demands": []}),
                },
                {
                    "agent_id": "agent2",
                    "agent_type": "patent_search",
                    "status": "pending",
                },
            ],
        )
        resp = client.post("/api/analysis/1/proceed")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "proceeding"

    def test_proceed_task_not_found(self, client):
        resp = client.post("/api/analysis/999/proceed")
        assert resp.status_code == 404, resp.text

    def test_proceed_no_workflow(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.post("/api/analysis/1/proceed")
        assert resp.status_code == 400, resp.text
        assert "工作流未启动" in resp.json()["detail"]

    def test_proceed_not_awaiting_rating(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_workflow(mock_db, 1, status="running")
        resp = client.post("/api/analysis/1/proceed")
        assert resp.status_code == 400, resp.text
        assert "不需要评分" in resp.json()["detail"]

    def test_proceed_with_ratings(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_workflow(
            mock_db,
            1,
            status="awaiting_rating",
            steps=[
                {
                    "agent_id": "agent1",
                    "agent_type": "problem_analysis",
                    "status": "completed",
                    "output": json.dumps({"demands": [{"id": "d1"}]}),
                },
                {
                    "agent_id": "agent2",
                    "agent_type": "patent_search",
                    "status": "pending",
                },
            ],
        )
        resp = client.post(
            "/api/analysis/1/proceed",
            json={"ratings": [{"demandId": "d1", "score": 4}]},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "proceeding"


class TestWorkflow:
    """Workflow 接口测试"""

    # ── GET /api/workflow/{task_id} ──

    def test_get_workflow_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_workflow(mock_db, 1, status="running")
        resp = client.get("/api/workflow/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["taskId"] == "1"
        assert data["status"] == "running"

    def test_get_workflow_task_not_found(self, client):
        resp = client.get("/api/workflow/999")
        assert resp.status_code == 404, resp.text

    def test_get_workflow_not_started(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.get("/api/workflow/1")
        assert resp.status_code == 404, resp.text
        assert "not yet started" in resp.json()["detail"]

    # ── POST /api/workflow/{task_id} ──

    def test_create_workflow_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.post("/api/workflow/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["taskId"] == "1"
        assert data["data"]["status"] == "idle"
        assert len(data["data"]["steps"]) == 6

    def test_create_workflow_task_not_found(self, client):
        resp = client.post("/api/workflow/999")
        assert resp.status_code == 404, resp.text

    def test_create_workflow_already_exists(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_workflow(mock_db, 1)
        resp = client.post("/api/workflow/1")
        assert resp.status_code == 400, resp.text
        assert "already exists" in resp.json()["detail"]

    # ── PATCH /api/workflow/{task_id}/step ──

    def test_update_step_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        agent1 = {
            "agent_id": "agent1",
            "agent_type": "problem_analysis",
            "status": "pending",
        }
        _seed_workflow(mock_db, 1, steps=[agent1])
        resp = client.patch(
            "/api/workflow/1/step",
            json={"agent_id": "agent1", "status": "running"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "running"

    def test_update_step_task_not_found(self, client):
        resp = client.patch(
            "/api/workflow/999/step",
            json={"agent_id": "agent1", "status": "running"},
        )
        assert resp.status_code == 404, resp.text

    def test_update_step_workflow_not_found(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.patch(
            "/api/workflow/1/step",
            json={"agent_id": "agent1", "status": "running"},
        )
        assert resp.status_code == 404, resp.text

    def test_update_step_unknown_agent(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_workflow(
            mock_db, 1, steps=[{"agent_id": "agent1", "agent_type": "test", "status": "pending"}]
        )
        resp = client.patch(
            "/api/workflow/1/step",
            json={"agent_id": "agent_unknown", "status": "running"},
        )
        assert resp.status_code == 400, resp.text
        assert "Unknown agent_id" in resp.json()["detail"]

    def test_update_step_transitions_to_completed(self, client, mock_db):
        _seed_task(mock_db, 1)
        agent1 = {
            "agent_id": "agent1",
            "agent_type": "problem_analysis",
            "status": "running",
            "started_at": "2024-01-01T00:00:00",
        }
        _seed_workflow(mock_db, 1, steps=[agent1])
        resp = client.patch(
            "/api/workflow/1/step",
            json={"agent_id": "agent1", "status": "completed"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "completed"


class TestSolutions:
    """Solutions 接口测试"""

    # ── GET /api/solutions/{task_id} ──

    def test_list_solutions_empty(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.get("/api/solutions/1")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []

    def test_list_solutions_with_data(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_solution(mock_db, 1, task_id=1, title="Sol A")
        _seed_solution(mock_db, 2, task_id=1, title="Sol B")
        resp = client.get("/api/solutions/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data) == 2
        titles = [d["title"] for d in data]
        assert "Sol A" in titles
        assert "Sol B" in titles

    def test_list_solutions_task_not_found(self, client):
        resp = client.get("/api/solutions/999")
        assert resp.status_code == 404, resp.text

    # ── GET /api/solutions/{task_id}/{solution_id} ──

    def test_get_solution_detail_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.get("/api/solutions/1/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["id"] == "1"
        assert data["taskId"] == "1"
        assert data["title"] == "Solution A"

    def test_get_solution_detail_not_found(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.get("/api/solutions/1/999")
        assert resp.status_code == 404, resp.text

    def test_get_solution_detail_task_not_found(self, client):
        resp = client.get("/api/solutions/999/1")
        assert resp.status_code == 404, resp.text

    # ── PUT /api/solutions/{task_id}/{solution_id} ──

    def test_update_rating_success(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.put("/api/solutions/1/1", json={"rating": 4})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["rating"] == 4

    def test_update_rating_out_of_range_low(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.put("/api/solutions/1/1", json={"rating": 0})
        assert resp.status_code == 400, resp.text
        assert "must be 1-5" in resp.json()["detail"]

    def test_update_rating_out_of_range_high(self, client, mock_db):
        _seed_task(mock_db, 1)
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.put("/api/solutions/1/1", json={"rating": 6})
        assert resp.status_code == 400, resp.text
        assert "must be 1-5" in resp.json()["detail"]

    def test_update_solution_not_found(self, client, mock_db):
        _seed_task(mock_db, 1)
        resp = client.put("/api/solutions/1/999", json={"rating": 3})
        assert resp.status_code == 404, resp.text

    def test_update_solution_task_not_found(self, client):
        resp = client.put("/api/solutions/999/1", json={"rating": 3})
        assert resp.status_code == 404, resp.text


class TestEvaluation:
    """Evaluation 接口测试"""

    # ── POST /api/evaluation/{solution_id} ──

    def test_evaluate_solution_not_found(self, client):
        resp = client.post("/api/evaluation/999")
        assert resp.status_code == 404, resp.text
        assert "方案不存在" in resp.json()["detail"]

    def test_evaluate_already_exists(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        _seed_evaluation(mock_db, 1, solution_id=1)
        resp = client.post("/api/evaluation/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["solutionId"] == "1"
        assert data["dimension"] == "innovation"
        assert data["score"] == 85.0

    def test_evaluate_ai_error(self, client, mock_db, monkeypatch):
        """When AI evaluation raises an exception, returns 500."""
        _seed_solution(mock_db, 1, task_id=1)
        # Fake the AI call to raise
        async def fake_ai_eval(sid, uid):
            msg = f"AI failed for solution {sid}"
            raise RuntimeError(msg)

        # The endpoint imports `evaluate_solution` from evaluation_service at
        # runtime, so monkeypatch the evaluation_service module-level name.
        monkeypatch.setattr(
            "app.algorithm.evaluation_service.evaluate_solution",
            fake_ai_eval,
        )
        resp = client.post("/api/evaluation/1")
        assert resp.status_code == 500, resp.text
        assert "评估失败" in resp.json()["detail"]

    # ── GET /api/evaluation/{solution_id}/latest ──

    def test_get_latest_evaluation_success(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        _seed_evaluation(mock_db, 1, solution_id=1)
        resp = client.get("/api/evaluation/1/latest")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["solutionId"] == "1"
        assert data["overallVerdict"] == "方案可行"

    def test_get_latest_evaluation_not_yet_evaluated(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.get("/api/evaluation/1/latest")
        assert resp.status_code == 404, resp.text

    def test_get_latest_evaluation_solution_not_found(self, client):
        resp = client.get("/api/evaluation/999/latest")
        assert resp.status_code == 404, resp.text

    # ── GET /api/evaluation/{solution_id}/history ──

    def test_get_evaluation_history_empty(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.get("/api/evaluation/1/history")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []

    def test_get_evaluation_history_with_data(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        _seed_evaluation(mock_db, 1, solution_id=1, dimension="innovation", score=85)
        _seed_evaluation(mock_db, 2, solution_id=1, dimension="feasibility", score=70)
        resp = client.get("/api/evaluation/1/history")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data) == 2
        dims = [d["dimension"] for d in data]
        assert "innovation" in dims
        assert "feasibility" in dims

    def test_get_evaluation_history_solution_not_found(self, client):
        # Endpoint does NOT check solution existence — returns empty array
        resp = client.get("/api/evaluation/999/history")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []


class TestFeedback:
    """Feedback 接口测试"""

    # ── POST /api/feedback ──

    def test_create_feedback_success(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.post(
            "/api/feedback",
            json={
                "solution_id": 1,
                "rating": 4,
                "feedback_type": "general",
                "comments": "很不错",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["solutionId"] == "1"
        assert data["rating"] == 4
        assert data["feedbackType"] == "general"
        assert data["comments"] == "很不错"

    def test_create_feedback_rating_out_of_range(self, client):
        resp = client.post(
            "/api/feedback",
            json={"solution_id": 1, "rating": 6},
        )
        assert resp.status_code == 400, resp.text
        assert "must be 1-5" in resp.json()["detail"]

    def test_create_feedback_solution_not_found(self, client):
        resp = client.post(
            "/api/feedback",
            json={"solution_id": 999, "rating": 3},
        )
        assert resp.status_code == 404, resp.text

    # ── GET /api/feedback/{solution_id} ──

    def test_get_feedback_empty(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        resp = client.get("/api/feedback/1")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []

    def test_get_feedback_with_data(self, client, mock_db):
        _seed_solution(mock_db, 1, task_id=1)
        # Pre-seed feedback directly in mock DB
        fb_tbl = mock_db._ensure_table("feedbacks")
        fb_tbl[1] = {
            "id": 1,
            "user_id": 1,
            "solution_id": 1,
            "rating": 5,
            "feedback_type": "general",
            "comments": "Excellent!",
            "created_at": "2024-01-01 00:00:00",
        }
        fb_tbl[2] = {
            "id": 2,
            "user_id": 1,
            "solution_id": 1,
            "rating": 4,
            "feedback_type": "bug",
            "comments": "Good",
            "created_at": "2024-01-02 00:00:00",
        }
        if mock_db._ids.get("feedbacks", 0) <= 2:
            mock_db._ids["feedbacks"] = 3
        resp = client.get("/api/feedback/1")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data) == 2
        ratings = [d["rating"] for d in data]
        assert 5 in ratings
        assert 4 in ratings
