# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**InnovOS** (智融创新操作系统) - AI-powered innovation problem-solving system using multi-agent workflows. Built with React 19 (TypeScript) frontend and FastAPI (Python) backend. Uses SQLite for development, with PostgreSQL for production.

## Build & Development Commands

```bash
# Install dependencies
cd backend && uv sync
cd frontend && npm install

# Start development environment (both frontend and backend)
make dev

# Start individually
make backend      # FastAPI on :8000
make frontend     # Vite dev server on :5173

# Build & test
make build        # Build frontend for production
make test         # Run test suite
make lint         # Run linting (frontend: ESLint, backend: type checking)
make clean        # Remove build artifacts

# Single test
cd backend && python -m pytest tests/test_<filename>.py -v
```

## Architecture

### Frontend (React 19 + TypeScript + Vite)

```
src/
├── api/           # API client wrappers with JWT auth
├── features/      # Feature-based modules (dashboard, auth, analysis, patents)
├── components/    # Reusable UI components (layout/, ui/, diagram/, workflow/)
├── store/         # Zustand 5 state management (10 stores total)
├── types/         # TypeScript interfaces
├── routes/        # React Router v7 route definitions
├── hooks/         # Custom React hooks
└── utils/         # Utility functions
```

**Key Patterns:**
- State management via Zustand stores (one per feature domain)
- All API calls through `src/api/` with automatic JWT token injection
- Glass morphism UI styling with TailwindCSS 4
- Feature-based code organization (feature directories contain page components + feature-specific logic)

### Backend (FastAPI + SQLite)

```
backend/app/
├── api/           # FastAPI routers (16 total, all mounted in main.py)
├── algorithm/     # ZR-IPM algorithm, AI clients, key manager, crypto utils
├── models/        # Pydantic schemas
├── tables/        # SQLite table definitions
├── data/          # Seed data and static resources
├── database.py    # SQLite connection & initialization
├── auth.py        # JWT authentication
└── seed.py        # Database seeding
```

**Key Patterns:**
- Direct SQLite with `sqlite3.Row` for dict-like access (no ORM)
- WAL journal mode for concurrent reads
- Key Manager: API key rotation, rate limiting, concurrent request handling
- AI integration via OpenAI-compatible SDK (DeepSeek-R1, Qwen-Turbo, Qwen-Max, BGE-M3)

### Multi-Agent Architecture (ZR-MoA)

```
User Input → Demand Insight Agent → Problem Modeling Agent → Patent Analysis Agent
            → Solution Generation Agent → Solution Evaluation Agent → Achievement Transformation Agent
```

**Core Algorithm:** ZR-IPM (智融创新问题映射) - 87.4% accuracy for problem identification

**Four-Dimension Evaluation Engine:**
- Innovation Assessment (patent similarity, tech evolution)
- Feasibility Assessment (constraint reasoning, rule validation)
- Completeness Assessment (reasoning chain verification, cross-validation)
- Achievement Transformation Assessment (patent applicability, industry scenario matching)

### Database Schema (10 tables in InnovOS_ACCOUNTS.db)

- `users` - User accounts with roles
- `tasks` - Problem-solving tasks
- `patents` - 100K+ patents for RAG
- `solutions` - Generated solutions
- `evaluations` - Four-dimension evaluation scores
- `feedbacks` - User feedback for learning
- `knowledge_base` - Semantic embeddings (vector storage)
- `keys` - Encrypted API keys with rotation
- `workflow_steps` - Multi-agent workflow state
- `principles` - Innovation principles

### Key Configuration

Backend: `.env` (see `.env.example`)
- `INNOVOS_ENCRYPT_KEY` - Fernet encryption key
- `INNOVOS_JWT_SECRET` - JWT signing secret
- `DATABASE_URL` - SQLite path (default: InnovOS_ACCOUNTS.db)
- API Keys configured via admin UI and stored encrypted

## Development Notes

- **Type Safety:** TypeScript strict mode (frontend), Python type hints enforced (backend)
- **Commit Style:** `<type>(<scope>): <description>` (feat, fix, refactor, docs, test)
- **Branch Strategy:** main → develop → feature/fix/refactor branches
- **CORS:** Allows `localhost:5173` and `localhost:5174` (Vite dev servers)
- **JWT Tokens:** 24-hour expiry, sent via `Authorization: Bearer <token>` header
- **Database Init:** Automatic on backend startup (`init_db()` + `seed_admin_user()`)
- **Dev Servers:** Backend on `:8000`, Frontend on `:5173`

## Documentation

- `/docs/` - Comprehensive Chinese documentation
- `/docs/architecture.md` - System architecture diagrams
- `/docs/development.md` - Code style and Git workflow
- `/docs/DEVELOPMENT_GUIDE.md` - Product vision and roadmap
