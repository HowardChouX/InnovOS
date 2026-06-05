from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.api import auth, tasks, analysis, patents, solutions, workflow, evaluation, feedback

init_db()

app = FastAPI(title="InnovOS API", description="创新智能平台后端 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(analysis.router)
app.include_router(patents.router)
app.include_router(solutions.router)
app.include_router(workflow.router)
app.include_router(evaluation.router)
app.include_router(feedback.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "InnovOS API is running"}
