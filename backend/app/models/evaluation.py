from pydantic import BaseModel


class EvaluationCreate(BaseModel):
    solution_id: int
    dimension: str = "comprehensive"
    score: float = 0
    details: dict = {}


class EvaluationResponse(BaseModel):
    id: str
    solution_id: str
    dimension: str
    score: float
    details: dict
    status: str
    created_at: str
