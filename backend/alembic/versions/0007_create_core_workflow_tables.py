"""create core workflow tables

Revision ID: 0007
Revises: 0006a
Create Date: 2026-07-30

包含 8 张业务核心表（按 FK 依赖顺序）：
1. tasks          — 主任务表（FK→users）
2. analyses       — 冲突分析（FK→tasks UNIQUE）
3. solutions      — 创新方案（FK→tasks）
4. workflows      — 工作流状态（FK→tasks UNIQUE）
5. patents        — 专利数据（无 FK）
6. evaluations    — 四维评估（FK→solutions, users）
7. feedbacks      — 用户反馈（FK→users, solutions）
8. problem_modelings — 问题建模（FK→tasks UNIQUE）

所有列与索引在 CREATE TABLE 时一次性写完（含 created_at/updated_at、is_active BOOLEAN 前置），
无需后续 ALTER。
"""
from alembic import op

revision = "0007"
down_revision = "0006a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. tasks ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")

    # ── 2. analyses ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
            center_node TEXT NOT NULL DEFAULT '{}',
            satellite_nodes TEXT NOT NULL DEFAULT '[]',
            edges TEXT NOT NULL DEFAULT '[]',
            principles TEXT NOT NULL DEFAULT '[]',
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_analyses_task_id ON analyses(task_id)")

    # ── 3. solutions ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS solutions (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            principles TEXT DEFAULT '[]',
            confidence_score INTEGER DEFAULT 0,
            patent_references TEXT DEFAULT '[]',
            rating INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_solutions_task_id ON solutions(task_id)")

    # ── 4. workflows ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'running',
            steps TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_workflows_task_id ON workflows(task_id)")

    # ── 5. patents ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS patents (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            abstract TEXT DEFAULT '',
            applicants TEXT DEFAULT '[]',
            inventors TEXT DEFAULT '[]',
            filing_date TEXT DEFAULT '',
            publication_date TEXT DEFAULT '',
            patent_number TEXT DEFAULT '',
            ipc_codes TEXT DEFAULT '[]',
            relevance_score INTEGER DEFAULT 0,
            publication_number TEXT DEFAULT '',
            claims TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_patents_relevance_score "
        "ON patents(relevance_score DESC)"
    )
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_patents_patent_number
        ON patents(patent_number) WHERE patent_number != ''
    """)

    # ── 6. evaluations ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id SERIAL PRIMARY KEY,
            solution_id INTEGER NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            dimension TEXT NOT NULL DEFAULT 'comprehensive',
            score REAL DEFAULT 0,
            details TEXT DEFAULT '{}',
            status TEXT DEFAULT 'completed',
            root_cause_cut BOOLEAN DEFAULT FALSE,
            original_contradiction_resolved BOOLEAN DEFAULT FALSE,
            new_contradictions TEXT DEFAULT '[]',
            function_deficits_filled TEXT DEFAULT '[]',
            new_harmful_interactions TEXT DEFAULT '[]',
            ifr_distance TEXT DEFAULT 'far',
            ifr_gap_description TEXT DEFAULT '',
            ifr_parameters_achieved TEXT DEFAULT '[]',
            overall_verdict TEXT DEFAULT 'failed',
            evolution_alignment REAL DEFAULT 0,
            aligned_laws TEXT DEFAULT '[]',
            misaligned_laws TEXT DEFAULT '[]',
            maturity TEXT DEFAULT '概念阶段',
            confidence REAL DEFAULT NULL,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_evaluations_solution_user "
        "ON evaluations(solution_id, user_id)"
    )

    # ── 7. feedbacks ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            solution_id INTEGER NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            feedback_type TEXT DEFAULT 'general',
            comments TEXT DEFAULT '',
            is_applied INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedbacks_solution_user "
        "ON feedbacks(solution_id, user_id)"
    )

    # ── 8. problem_modelings ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS problem_modelings (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
            problem_elements TEXT NOT NULL DEFAULT '{}',
            conflicts TEXT NOT NULL DEFAULT '[]',
            recommended_principles TEXT NOT NULL DEFAULT '[]',
            innovation_directions TEXT NOT NULL DEFAULT '[]',
            model_structure TEXT NOT NULL DEFAULT '{}',
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_problem_modelings_task_id "
        "ON problem_modelings(task_id)"
    )


def downgrade() -> None:
    # 反向 DROP，顺序与创建相反（FK 引用方先 DROP）
    for table in (
        "problem_modelings",
        "feedbacks",
        "evaluations",
        "patents",
        "workflows",
        "solutions",
        "analyses",
        "tasks",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
