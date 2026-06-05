from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    solution_id: int
    rating: int
    feedback_type: str = "general"
    comments: str = ""


class FeedbackResponse(BaseModel):
    id: str
    user_id: str
    solution_id: str
    rating: int
    feedback_type: str
    comments: str
    created_at: str
