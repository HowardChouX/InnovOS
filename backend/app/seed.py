import json
from app.database import get_db

SEED_PATENTS = [
    {
        "title": "一种高安全性固态电池及其制备方法",
        "abstract": "本发明提供了一种高安全性固态电池，通过采用硫化物固态电解质和界面改性层。",
        "applicants": json.dumps(["宁德时代新能源科技股份有限公司"]),
        "inventors": json.dumps(["张明", "李华"]),
        "filing_date": "2023-05-16", "publication_date": "2024-01-20",
        "patent_number": "CN202310456789.1",
        "ipc_codes": json.dumps(["H01M10/056", "H01M10/0525"]),
        "relevance_score": 98,
    },
    {
        "title": "一种提高锂离子电池循环寿命的电极材料及其制备方法",
        "abstract": "本发明涉及一种掺杂改性的三元正极材料。",
        "applicants": json.dumps(["比亚迪股份有限公司"]),
        "inventors": json.dumps(["赵六", "钱七"]),
        "filing_date": "2022-11-03", "publication_date": "2023-10-25",
        "patent_number": "CN202210987654.8",
        "ipc_codes": json.dumps(["H01M4/36", "H01M4/505"]),
        "relevance_score": 95,
    },
    {
        "title": "一种电池热失控抑制方法及电池模组",
        "abstract": "本发明涉及一种电池热失控抑制方法。",
        "applicants": json.dumps(["华为技术有限公司"]),
        "inventors": json.dumps(["吴十一", "郑十二"]),
        "filing_date": "2022-02-21", "publication_date": "2023-03-10",
        "patent_number": "CN202210123456.3",
        "ipc_codes": json.dumps(["H01M10/6556", "H01M10/613"]),
        "relevance_score": 93,
    },
]


def seed_patents():
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM patents").fetchone()[0]
    if count == 0:
        for p in SEED_PATENTS:
            db.execute(
                """INSERT INTO patents (title, abstract, applicants, inventors,
                   filing_date, publication_date, patent_number, ipc_codes, relevance_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p["title"], p["abstract"], p["applicants"], p["inventors"],
                 p["filing_date"], p["publication_date"], p["patent_number"],
                 p["ipc_codes"], p["relevance_score"]),
            )
        db.commit()
    db.close()


def seed_demo_task(db, user_id: int):
    cursor = db.execute(
        "INSERT INTO tasks (user_id, title, description, tags, status) VALUES (?, ?, ?, ?, ?)",
         (user_id, "[Demo] 新能源汽车电池热管理技术改进",
          "如何在保证电池能量密度的同时，提高其安全性并延长循环寿命？",
          json.dumps(["电池安全", "能量密度", "循环寿命", "demo"]), "completed"),
    )
    task_id = cursor.lastrowid

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
         '["复合材料原理","参数变化原理"]', 92, '["p1","p3"]', 5),
        ("结构设计优化 + 热管理系统",
         "优化电池内部结构设计，引入先进的相变材料热管理系统，在保证能量密度的前提下实现高效热管理。",
         '["分割原理","动态化原理"]', 85, '["p4"]', 4),
        ("新型电解液 + 功能添加剂",
         "开发新型电解液配方体系，引入多功能添加剂同步提升离子电导率、阻燃性能和电极相容性。",
         '["复合材料原理","局部质量原理"]', 80, '["p5"]', 4),
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
