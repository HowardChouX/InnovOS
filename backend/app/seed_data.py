"""
Seed data from local development into Docker PostgreSQL.

Run on first startup to populate patent/providers/models data.
Uses ON CONFLICT to be idempotent.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).parent.parent / "scripts" / "seed_data.sql"


def seed_database(db):
    """Import seed data if patents table is empty."""
    from app.database import get_db as _get_conn

    # Check if data already exists
    row = db.execute("SELECT COUNT(*) FROM patents").fetchone()
    if row and row[0] > 0:
        logger.info("Seed data already exists (%s patents), skipping", row[0])
        return

    if not SEED_FILE.exists():
        logger.info("No seed file found at %s, skipping", SEED_FILE)
        return

    logger.info("Seeding database from %s ...", SEED_FILE)

    sql = SEED_FILE.read_text()
    # Parse COPY blocks into INSERT ... ON CONFLICT DO NOTHING
    _import_copy_blocks(db, sql)
    db.commit()
    logger.info("Database seeding complete")


def _import_copy_blocks(db, sql: str):
    """Parse pg_dump COPY format and execute as INSERT with ON CONFLICT."""
    lines = sql.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("COPY ") and line.endswith(" FROM stdin;"):
            # Extract table name
            parts = line.split()
            table = parts[1].split(".")[-1]  # public.table -> table
            columns_part = line[line.index("(") + 1 : line.rindex(")")] if "(" in line else ""
            columns = [c.strip() for c in columns_part.split(",")] if columns_part else []

            # Read data rows until \.
            rows = []
            i += 1
            while i < len(lines) and lines[i].strip() != "\\.":
                row = lines[i].strip()
                if row:
                    vals = _parse_copy_row(row, len(columns) if columns else 0)
                    rows.append(vals)
                i += 1

            if rows:
                pk_col = _get_pk(table)
                _bulk_insert(db, table, columns if columns else None, rows, pk_col)
        i += 1


def _parse_copy_row(line: str, col_count: int) -> list:
    """Parse a single COPY row, handling escaped values correctly."""
    vals = []
    buf = []
    in_quotes = False
    in_array = 0
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            nxt = line[i + 1]
            if nxt == "N":
                buf.append(None)
                i += 2
                continue
            elif nxt == "t":
                buf.append("\t")
                i += 2
                continue
            elif nxt == "n":
                buf.append("\n")
                i += 2
                continue
            else:
                buf.append(nxt)
                i += 2
                continue
        if ch == '"' and not in_array:
            in_quotes = not in_quotes
            i += 1
            continue
        if ch == "{" and not in_quotes:
            in_array += 1
        if ch == "}" and not in_quotes:
            in_array -= 1
        if ch == "\t" and not in_quotes and in_array == 0:
            vals.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        vals.append("".join(buf))
    # Pad with None if needed
    while len(vals) < col_count:
        vals.append(None)
    return vals


def _get_pk(table: str) -> str | None:
    """Guess primary key column."""
    pk_map = {
        "patents": "id",
        "patent_vectors": "id",
        "model_providers": "id",
        "models": None,  # composite PK (provider_id, model_id)
    }
    return pk_map.get(table)


def _bulk_insert(db, table: str, columns: list[str] | None, rows: list[list], pk_col: str | None):
    """INSERT rows with ON CONFLICT handling."""
    if not rows:
        return
    if not columns:
        logger.warning("No columns for table %s, skipping %s rows", table, len(rows))
        return

    placeholders = ", ".join(f"? " for _ in columns)
    col_names = ", ".join(columns)
    conflict = f"ON CONFLICT ({pk_col}) DO NOTHING" if pk_col else "ON CONFLICT DO NOTHING"
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) {conflict}"

    for vals in rows:
        try:
            # Convert \N to None, parse arrays
            clean = [_clean_val(v, col) for v, col in zip(vals, columns)]
            db.execute(sql, clean)
        except Exception as e:
            logger.warning("Failed to insert row into %s: %s (first col: %s)", table, e, vals[0] if vals else "?")


def _clean_val(val, col: str | None):
    """Clean and convert COPY values."""
    if val is None or val == r"\N":
        return None
    # Try to parse JSON arrays (for vector columns)
    if isinstance(val, str) and val.startswith("[") and val.endswith("]"):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val
