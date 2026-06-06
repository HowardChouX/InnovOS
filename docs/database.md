# InnovOS 数据库设计

数据库文件：`backend/InnovOS_ACCOUNTS.db`

## 1. 数据库配置

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
```

## 2. 表结构

### 2.1 用户表 (users)

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
);
```

### 2.2 任务表 (tasks)

```sql
CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    tags        TEXT DEFAULT '[]',
    status      TEXT DEFAULT 'pending',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 2.3 分析结果表 (analyses)

冲突图谱数据，存储中心节点、卫星节点、边关系和 TRIZ 原理。

```sql
CREATE TABLE analyses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id        INTEGER NOT NULL UNIQUE,
    center_node    TEXT NOT NULL DEFAULT '{}',
    satellite_nodes TEXT NOT NULL DEFAULT '[]',
    edges          TEXT NOT NULL DEFAULT '[]',
    principles     TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 2.4 解决方案表 (solutions)

```sql
CREATE TABLE solutions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id           INTEGER NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL,
    principles        TEXT DEFAULT '[]',
    confidence_score  INTEGER DEFAULT 0,
    patent_references TEXT DEFAULT '[]',
    rating            INTEGER DEFAULT 0,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 2.5 工作流表 (workflows)

```sql
CREATE TABLE workflows (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL UNIQUE,
    status     TEXT DEFAULT 'running',
    steps      TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 2.6 专利表 (patents)

```sql
CREATE TABLE patents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    abstract         TEXT DEFAULT '',
    applicants       TEXT DEFAULT '[]',
    inventors        TEXT DEFAULT '[]',
    filing_date      TEXT DEFAULT '',
    publication_date TEXT DEFAULT '',
    patent_number    TEXT DEFAULT '',
    ipc_codes        TEXT DEFAULT '[]',
    relevance_score  INTEGER DEFAULT 0
);
```

### 2.7 API Key 表 (api_keys)

```sql
CREATE TABLE api_keys (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name         TEXT NOT NULL,
    api_key          TEXT NOT NULL,
    api_base_url     TEXT DEFAULT 'https://api.deepseek.com',
    api_model        TEXT DEFAULT '',
    is_active        INTEGER DEFAULT 1,
    priority         INTEGER DEFAULT 0,
    max_rpm          INTEGER DEFAULT 60,
    current_rpm      INTEGER DEFAULT 0,
    last_reset_at    TEXT,
    last_used_at     TEXT,
    request_count    INTEGER DEFAULT 0,
    created_at       TEXT DEFAULT (datetime('now'))
);
```

### 2.7 评估记录表 (evaluations)

```sql
CREATE TABLE evaluations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    solution_id INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    dimension   TEXT NOT NULL DEFAULT 'comprehensive',
    score       REAL DEFAULT 0,
    details     TEXT DEFAULT '{}',
    status      TEXT DEFAULT 'completed',
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (solution_id) REFERENCES solutions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 2.8 反馈记录表 (feedbacks)

```sql
CREATE TABLE feedbacks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    solution_id   INTEGER NOT NULL,
    rating        INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
    feedback_type TEXT NOT NULL DEFAULT 'general',
    comments      TEXT DEFAULT '',
    is_applied    INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (solution_id) REFERENCES solutions(id)
);
```

### 2.9 审计日志表 (audit_logs)

```sql
CREATE TABLE audit_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER REFERENCES users(id),
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   INTEGER,
    detail        TEXT DEFAULT '{}',
    ip_address    TEXT DEFAULT '',
    status        TEXT DEFAULT 'success',
    created_at    TEXT DEFAULT (datetime('now'))
);
```

## 3. 关系图

```
users ──< tasks ──< analyses (1:1)
  │          │
  │          ├──< solutions
  │          │
  │          └──< workflows (1:1)
  │
  ├──< evaluations
  │
  ├──< feedbacks
  │
  └──< audit_logs

patents (独立表，无外键)

api_keys (独立表，AI Key 池管理)
```
