import sqlite3


def init_model_providers(db):
    """Initialize model_providers table (SQLite version — kept for direct testing)."""
    from app.tables.pg_schema import init_model_providers as _pg_init
    _pg_init(db)
