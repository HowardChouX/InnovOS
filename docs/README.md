# InnovOS 智融创新操作系统

AI 驱动的多 Agent 协同创新问题求解系统。

## 快速开始

```bash
make install   # 安装依赖
make dev       # 启动开发环境（前端 :5173 + 后端 :8000）
```

## 文档

- [**开发文档**](./DEVELOPMENT_GUIDE.md) — 项目结构、数据库、API、开发规范、实施计划
- [Key 管理系统](./key-management.md) — API Key 轮询、加密、限流
- [AI 集成文档](./ai-integration.md) — AI 客户端、ZR-IPM 引擎
- [开发规范](./development.md) — 代码风格、Git 工作流
- [生产部署](./production.md) — 环境配置与部署

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 19 + TypeScript + Vite 8 + Zustand 5 + TailwindCSS 4 |
| 后端 | FastAPI + SQLite（开发）/ PostgreSQL（生产） |
| AI | ZR-MoA 多模型架构（DeepSeek-R1 / Qwen-Turbo / Qwen-Max / BGE-M3） |
| 核心算法 | ZR-IPM 智融创新问题映射（准确率 87.4%） |

## 许可证

私有项目 — 济南一竖光年人工智能科技有限公司
