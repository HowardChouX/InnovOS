import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "InnovOS_ACCOUNTS.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    from app.tables import init_all_tables
    conn = get_db()
    init_all_tables(conn)
    conn.close()
