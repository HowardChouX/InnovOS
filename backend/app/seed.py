import json
import logging
from app.database import get_db
from app.auth import hash_password

logger = logging.getLogger(__name__)

SEED_ADMIN_USERNAME = "InnovOS2026@admin"
SEED_ADMIN_PASSWORD = "K9#mP7$xR2!vL8"


def seed_admin_user():
    """创建/重置默认管理员账号"""
    db = get_db()
    password_hash = hash_password(SEED_ADMIN_PASSWORD)

    # 删除旧的admin用户避免冲突
    db.execute("DELETE FROM users WHERE username='admin' OR username='InnovOS'")
    db.commit()

    existing = db.execute("SELECT id FROM users WHERE username=?", (SEED_ADMIN_USERNAME,)).fetchone()

    if not existing:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (SEED_ADMIN_USERNAME, password_hash, "admin")
        )
        db.commit()
        logger.info(f"管理员账号已创建: {SEED_ADMIN_USERNAME}")
    else:
        db.execute(
            "UPDATE users SET password_hash=?, role='admin' WHERE username=?",
            (password_hash, SEED_ADMIN_USERNAME)
        )
        db.commit()
        logger.info(f"管理员密码已重置: {SEED_ADMIN_USERNAME}")

    logger.warning("请在生产环境中修改默认密码！")
    db.close()


def seed_demo_task(db, user_id: int):
    cursor = db.execute(
        "INSERT INTO tasks (user_id, title, description, tags, status) VALUES (?, ?, ?, ?, ?) RETURNING id",
         (user_id, "[Demo] 新能源汽车电池热管理技术改进",
          "如何在保证电池能量密度的同时，提高其安全性并延长循环寿命？",
          json.dumps(["电池安全", "能量密度", "循环寿命", "demo"]), "completed"),
    )
    task_id = cursor.fetchone()["id"]

    db.execute(
        "INSERT INTO analyses (task_id, center_node, satellite_nodes, edges, principles) VALUES (?,?,?,?,?)",
        (task_id,
         json.dumps({"id": "center", "label": "核心冲突", "description": "提高能量密度 vs 保证安全性", "type": "center"}),
         json.dumps([
             {"id": "s1", "label": "能量密度", "sublabel": "(提升)", "description": "提高单位体积/重量能量储存量", "type": "satellite", "color": "#06b6d4", "position": "top"},
             {"id": "s2", "label": "安全性", "sublabel": "(提升)", "description": "防止热失控、短路等安全风险", "type": "satellite", "color": "#10b981", "position": "right"},
             {"id": "s3", "label": "循环寿命", "sublabel": "(延长)", "description": "延长电池充放电循环次数", "type": "satellite", "color": "#8b5cf6", "position": "bottom"},
             {"id": "s4", "label": "副作用", "sublabel": "发热问题 (增加)", "description": "高能量密度导致发热量增大", "type": "satellite", "color": "#f59e0b", "position": "left"},
         ]),
         json.dumps([{"sourceId": "center", "targetId": "s1", "label": "冲突"}, {"sourceId": "center", "targetId": "s2", "label": "冲突"}, {"sourceId": "center", "targetId": "s3", "label": "关联"}, {"sourceId": "center", "targetId": "s4", "label": "导致"}]),
         json.dumps(["分割原理", "动态化原理", "复合材料原理", "参数变化原理"])),
    )

    defaults = [
        ("固态电池 + 界面改性技术",
         "通过固态电解质替换液态电解质，结合界面改性技术和多层结构设计，在提升能量密度的同时有效抑制热失控，提高安全性并延长循环寿命。",
         '["复合材料原理","参数变化原理"]', 92, '[]', 5),
        ("结构设计优化 + 热管理系统",
         "优化电池内部结构设计，引入先进的相变材料热管理系统，在保证能量密度的前提下实现高效热管理。",
         '["分割原理","动态化原理"]', 85, '[]', 4),
        ("新型电解液 + 功能添加剂",
         "开发新型电解液配方体系，引入多功能添加剂同步提升离子电导率、阻燃性能和电极相容性。",
         '["复合材料原理","局部质量原理"]', 80, '[]', 4),
    ]
    for title, desc, principles, score, refs, rating in defaults:
        db.execute(
            "INSERT INTO solutions (task_id, title, description, principles, confidence_score, patent_references, rating) VALUES (?,?,?,?,?,?,?)",
            (task_id, title, desc, principles, score, refs, rating),
        )

    steps = json.dumps([
        {"agentId": "agent1", "agentType": "problem_analysis", "agentLabel": "需求洞察Agent", "status": "completed",
         "description": "理解用户需求，提取关键要素", "startedAt": "", "completedAt": "", "duration": "2.1s"},
        {"agentId": "agent2", "agentType": "patent_search", "agentLabel": "问题建模Agent", "status": "completed",
         "description": "构建问题模型，识别核心冲突", "startedAt": "", "completedAt": "", "duration": "3.4s"},
        {"agentId": "agent5", "agentType": "patent_search", "agentLabel": "专利分析Agent", "status": "completed",
         "description": "检索相关专利，分析技术方案", "startedAt": "", "completedAt": "", "duration": "8.7s"},
        {"agentId": "agent3", "agentType": "solution_gen", "agentLabel": "方案生成Agent", "status": "running",
         "description": "生成创新方案，整合多源知识", "startedAt": "", "duration": "2.8s"},
        {"agentId": "agent4", "agentType": "evaluation", "agentLabel": "方案评估Agent", "status": "pending",
         "description": "评估方案可行性与创新性"},
        {"agentId": "agent6", "agentType": "evaluation", "agentLabel": "成果转化Agent", "status": "pending",
         "description": "输出结构化成果，支持转化"},
    ])
    db.execute("INSERT INTO workflows (task_id, status, steps) VALUES (?,?,?)", (task_id, "running", steps))
    db.commit()
