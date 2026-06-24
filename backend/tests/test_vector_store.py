"""
Tests for VectorStore — hybrid search, CRUD, batch operations.
"""
import json
import sys
import re
import pytest
from unittest.mock import MagicMock


# ════════════════════════════════════════════════════════════════
#  Fixtures: numpy mock (needed by all search tests)
# ════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_numpy(monkeypatch):
    """Mock numpy for cosine similarity calculations.

    Provides ``np.array``, ``np.linalg.norm``, ``np.dot``, and ``np.float32``.
    """
    mock_np = MagicMock()
    # Return a real list so we can compute dot products below
    mock_np.array.side_effect = lambda x, dtype=None: list(x) if isinstance(x, (list, tuple)) else [x]
    mock_np.linalg.norm.return_value = 1.0  # fake norm so division never blows up
    mock_np.dot.side_effect = lambda a, b: sum(x * y for x, y in zip(a, b))
    mock_np.float32 = float
    monkeypatch.setitem(sys.modules, "numpy", mock_np)


# ════════════════════════════════════════════════════════════════
#  Helper: patch get_db at global + module level
# ════════════════════════════════════════════════════════════════

def _patch_get_db(monkeypatch, mock_db):
    """Patch get_db in both app.database and the vector_store module.

    vector_store.py does ``from app.database import get_db`` at module level,
    so changing ``app.database.get_db`` alone doesn't affect the cached local
    reference once the module has been imported.  We must patch both.
    """
    monkeypatch.setattr("app.database.get_db", lambda: mock_db)
    monkeypatch.setattr("app.algorithm.knowledge.vector_store.get_db", lambda: mock_db)


def _make_row(id_: int, item_id: str, chunk_idx: int, text: str,
              score_or_embedding: list[float] = None) -> dict:
    """Build a dict shaped like a PG row for ``_search_pg`` (vector mode)."""
    return {
        "id": id_,
        "item_id": item_id,
        "chunk_index": chunk_idx,
        "text": text,
        "score": 0.0,  # placeholder; tests override via _fetchall_result directly
    }


def _make_hybrid_row(id_: int, item_id: str, chunk_idx: int, text: str,
                     cosine_score: float = 0.0, text_score: float = 0.0) -> dict:
    """Build a dict shaped like a PG row for ``_search_pg`` (hybrid mode)."""
    return {
        "id": id_,
        "item_id": item_id,
        "chunk_index": chunk_idx,
        "text": text,
        "cosine_score": cosine_score,
        "text_score": text_score,
    }


# ════════════════════════════════════════════════════════════════
#  Vector CRUD
# ════════════════════════════════════════════════════════════════


def test_replace_by_external_id_inserts_vectors(monkeypatch, mock_db):
    """Verify DELETE + INSERT SQL calls for a non-empty vector replace."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    vs = VectorStore(user_id=1, dimensions=1024)

    vectors = [[0.1, 0.2], [0.3, 0.4]]
    metadata = [
        {"chunk_idx": 0, "text": "first chunk"},
        {"chunk_idx": 1, "text": "second chunk"},
    ]

    vs.replace_by_external_id("base_1", "item_1", vectors, metadata)

    # 1 DELETE + 2 INSERTs
    assert len(mock_db.all_sql) == 3, \
        "Expected 3 SQL statements (1 DELETE + 2 INSERT)"

    # First statement is DELETE
    assert "DELETE FROM knowledge_vectors" in mock_db.all_sql[0]
    assert "item_id = %s" in mock_db.all_sql[0]

    # Remaining statements are INSERTs
    for sql in mock_db.all_sql[1:]:
        assert "INSERT INTO knowledge_vectors" in sql

    # Verify DELETE was called with correct item_id
    delete_entry = mock_db.cursor.history[0]
    assert delete_entry[1] == ("item_1", 1)


def test_replace_by_external_id_empty_clears_vectors(monkeypatch, mock_db):
    """Empty vectors → only DELETE called (delegates to delete_by_external_id)."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    vs = VectorStore(user_id=1, dimensions=1024)
    vs.replace_by_external_id("base_1", "item_1", [], [])

    # Only DELETE should be recorded (no INSERT)
    assert len(mock_db.all_sql) == 1
    assert "DELETE FROM knowledge_vectors" in mock_db.all_sql[0]
    assert "item_id = %s" in mock_db.all_sql[0]


def test_delete_by_external_id_removes_vectors(monkeypatch, mock_db):
    """Verify DELETE SQL with item_id condition."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    vs = VectorStore(user_id=1, dimensions=1024)
    vs.delete_by_external_id("item_42")

    assert len(mock_db.all_sql) == 1
    assert "DELETE FROM knowledge_vectors" in mock_db.all_sql[0]
    assert "item_id = %s" in mock_db.all_sql[0]

    delete_entry = mock_db.cursor.history[0]
    assert delete_entry[1] == ("item_42", 1)


# ════════════════════════════════════════════════════════════════
#  Search Modes
# ════════════════════════════════════════════════════════════════


def test_search_vector_mode_cosine_only(monkeypatch, mock_db):
    """Mock fetchall returns vectors; verify sorted by cosine score."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    # query = [1, 0, 0]; rows have decreasing dot-product similarity
    mock_db.cursor._fetchall_result = [
        {"id": 1, "item_id": "a", "chunk_index": 0, "text": "text a", "score": 0.95},
        {"id": 2, "item_id": "b", "chunk_index": 0, "text": "text b", "score": 0.5},
        {"id": 3, "item_id": "c", "chunk_index": 0, "text": "text c", "score": -0.8},
    ]

    vs = VectorStore(user_id=1, dimensions=3)
    results = vs.search(
        base_id="base_1",
        query_vector=[1.0, 0.0, 0.0],
        top_k=5,
        mode="vector",
    )

    assert len(results) == 3
    # Results must be sorted by score descending
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True), \
        "Results should be sorted by score descending"
    # a has highest dot product (0.95)
    assert results[0]["item_id"] == "a"


def test_search_hybrid_mode_blends_scores(monkeypatch, mock_db):
    """Hybrid mode with alpha=0.5 blends dot-product + keyword scores."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    # row_a: high cosine, but no keyword match
    # row_b: lower cosine, but strong keyword match → wins with hybrid
    mock_db.cursor._fetchall_result = [
        _make_hybrid_row(1, "a", 0, "unrelated content here", cosine_score=0.95, text_score=0.0),
        _make_hybrid_row(2, "b", 0, "hello world greetings", cosine_score=0.5, text_score=1.0),
    ]

    vs = VectorStore(user_id=1, dimensions=3)

    # --- hybrid mode ---
    hybrid_results = vs.search(
        base_id="base_1",
        query_vector=[1.0, 0.0, 0.0],
        top_k=5,
        query_text="hello world",
        mode="hybrid",
        alpha=0.5,
    )

    assert len(hybrid_results) == 2
    scores = [r["score"] for r in hybrid_results]
    assert scores == sorted(scores, reverse=True)

    # text_scores: [0.0, 1.0] → max=1.0 → normalized: [0.0, 1.0]
    # blended = (1-0.5)*cosine + 0.5*text_norm
    # row_a: 0.5*0.95 + 0.5*0.0 = 0.475
    # row_b: 0.5*0.5  + 0.5*1.0 = 0.75
    # So row_b (item_id="b") should be first
    assert hybrid_results[0]["item_id"] == "b", \
        "Hybrid mode should rank keyword-matched result higher"

    # --- pure vector mode for comparison ---
    mock_db.cursor._fetchall_result = [
        {"id": 1, "item_id": "a", "chunk_index": 0, "text": "unrelated content here", "score": 0.95},
        {"id": 2, "item_id": "b", "chunk_index": 0, "text": "hello world greetings", "score": 0.5},
    ]
    vector_results = vs.search(
        base_id="base_1",
        query_vector=[1.0, 0.0, 0.0],
        top_k=5,
        mode="vector",
    )
    assert vector_results[0]["item_id"] == "a", \
        "Pure vector mode should rank a higher"


def test_search_empty_base_returns_empty(monkeypatch, mock_db, mock_numpy):
    """Empty fetchall returns empty list."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    mock_db.cursor._fetchall_result = []

    vs = VectorStore(user_id=1, dimensions=2)
    results = vs.search(
        base_id="empty_base",
        query_vector=[1.0, 0.0],
        top_k=5,
    )

    assert results == []


# ════════════════════════════════════════════════════════════════
#  Hybrid Search Logic
# ════════════════════════════════════════════════════════════════


def test_hybrid_keyword_matching(monkeypatch, mock_db):
    """Directly verify keyword match computation with pure-keyword (alpha=1)."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    # All rows have identical vector → same dot product, keyword match is the differentiator
    mock_db.cursor._fetchall_result = [
        _make_hybrid_row(1, "a", 0, "hello there world", cosine_score=0.5, text_score=1.0),
        _make_hybrid_row(2, "b", 0, "hello only here", cosine_score=0.5, text_score=0.5),
        _make_hybrid_row(3, "c", 0, "no match at all", cosine_score=0.5, text_score=0.0),
    ]

    vs = VectorStore(user_id=1, dimensions=3)
    results = vs.search(
        base_id="base_1",
        query_vector=[1.0, 0.0, 0.0],
        top_k=5,
        query_text="hello world",
        mode="hybrid",
        alpha=1.0,  # pure keyword — score == bm25
    )

    assert len(results) == 3

    # text_scores: [1.0, 0.5, 0.0] → max=1.0 → normalized: [1.0, 0.5, 0.0]
    # blended with alpha=1.0 → score = text_norm
    # row_a should be first (1.0)
    # row_b second (0.5)
    # row_c third (0.0)
    assert results[0]["item_id"] == "a"
    assert abs(results[0]["score"] - 1.0) < 1e-6
    assert results[1]["item_id"] == "b"
    assert abs(results[1]["score"] - 0.5) < 1e-6
    assert results[2]["item_id"] == "c"
    assert abs(results[2]["score"] - 0.0) < 1e-6


def test_hybrid_alpha_zero_equals_vector(monkeypatch, mock_db):
    """With alpha=0.0, hybrid results are identical to vector-only results."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    # Vector mode results need "score" key
    mock_db.cursor._fetchall_result = [
        {"id": 1, "item_id": "a", "chunk_index": 0, "text": "some text", "score": 0.9},
        {"id": 2, "item_id": "b", "chunk_index": 0, "text": "hello world", "score": 0.5},
    ]
    vs = VectorStore(user_id=1, dimensions=2)

    vector_results = vs.search(
        base_id="base_1", query_vector=[1.0, 0.0], top_k=5, mode="vector",
    )

    # Hybrid mode with alpha=0.0 internally uses _search_pg with non-hybrid branch
    # so it also expects "score" key
    hybrid_results = vs.search(
        base_id="base_1", query_vector=[1.0, 0.0], top_k=5,
        query_text="hello world", mode="hybrid", alpha=0.0,
    )

    assert len(vector_results) == len(hybrid_results)
    for vr, hr in zip(vector_results, hybrid_results):
        assert vr["item_id"] == hr["item_id"]
        assert abs(vr["score"] - hr["score"]) < 1e-6, \
            f"Scores differ for {vr['item_id']}: {vr['score']} vs {hr['score']}"


def test_search_count_queries(monkeypatch, mock_db):
    """Verify count() emits COUNT(*) query."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    mock_db.cursor._fetchone_result = {"cnt": 7}

    vs = VectorStore(user_id=1, dimensions=1024)

    # — count by base_id —
    count = vs.count(base_id="base_1")
    assert count == 7
    assert "SELECT COUNT(*)" in mock_db.all_sql[0]
    assert "WHERE base_id = %s" in mock_db.all_sql[0]

    # — count all (no base_id) —
    mock_db.all_sql.clear()
    mock_db.cursor.history.clear()
    mock_db.cursor._fetchone_result = {"cnt": 42}

    count_all = vs.count()
    assert count_all == 42
    assert "SELECT COUNT(*)" in mock_db.all_sql[0]
    assert "WHERE user_id = %s" in mock_db.all_sql[0]


# ════════════════════════════════════════════════════════════════
#  Batch Delete
# ════════════════════════════════════════════════════════════════


def test_delete_by_external_ids_uses_IN_clause(monkeypatch, mock_db):
    """Verify DELETE uses ``IN (?,?,?)`` with correct params."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    vs = VectorStore(user_id=1, dimensions=1024)
    vs.delete_by_external_ids(["id1", "id2", "id3"])

    assert len(mock_db.all_sql) == 1
    sql = mock_db.all_sql[0]
    assert "DELETE FROM knowledge_vectors" in sql
    # The IN clause should have three %s placeholders
    assert "IN (%s,%s,%s)" in sql, \
        "Expected IN clause with 3 comma-separated placeholders"

    delete_entry = mock_db.cursor.history[0]
    assert delete_entry[1] == ("id1", "id2", "id3", 1)


def test_delete_by_external_ids_empty_list_does_nothing(monkeypatch, mock_db):
    """Empty item_ids list → no SQL is executed."""
    _patch_get_db(monkeypatch, mock_db)

    from app.algorithm.knowledge.vector_store import VectorStore

    vs = VectorStore(user_id=1, dimensions=1024)
    vs.delete_by_external_ids([])

    assert mock_db.all_sql == [], "No SQL should be executed for empty list"
