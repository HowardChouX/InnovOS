"""create knowledge_vectors + pgvector extension

Revision ID: 0014
Revises: 0011
Create Date: 2026-07-30

启用 pgvector 扩展 + 创建 knowledge_vectors 表(向量存储)。
FK 关系(到 users / knowledge_bases / knowledge_items)直接写在 CREATE TABLE 中，
HNSW 索引用 SAVEPOINT 包裹以兼容老版本 pgvector。
"""
from alembic import op

revision = "0014"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. pgvector extension (必须在 vector(4096) 类型前)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. knowledge_vectors (FK inline)
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_vectors (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            base_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            text TEXT NOT NULL,
            embedding vector(4096),
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_base_item "
        "ON knowledge_vectors(base_id, item_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_user_base "
        "ON knowledge_vectors(user_id, base_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_item_id "
        "ON knowledge_vectors(item_id)"
    )

    # 3. HNSW 索引（SAVEPOINT 包裹，兼容老 pgvector）
    op.execute("SAVEPOINT sp_hnsw")
    try:
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_embedding
            ON knowledge_vectors USING hnsw (embedding vector_cosine_ops)
        """)
        op.execute("RELEASE SAVEPOINT sp_hnsw")
    except Exception:
        op.execute("ROLLBACK TO SAVEPOINT sp_hnsw")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_knowledge_vectors_embedding")
    op.execute("DROP INDEX IF EXISTS idx_knowledge_vectors_item_id")
    op.execute("DROP INDEX IF EXISTS idx_knowledge_vectors_user_base")
    op.execute("DROP INDEX IF EXISTS idx_knowledge_vectors_base_item")
    op.execute("DROP TABLE IF EXISTS knowledge_vectors")
