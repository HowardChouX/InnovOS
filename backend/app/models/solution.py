from pydantic import BaseModel


class Solution(BaseModel):
    id: str
    task_id: str
    title: str
    description: str
    principles: list[str]
    confidence_score: int
    patent_references: list[str]
    rating: int
