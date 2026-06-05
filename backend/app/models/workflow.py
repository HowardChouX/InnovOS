from pydantic import BaseModel
from typing import Optional


class AgentStep(BaseModel):
    agent_id: str
    agent_type: str
    agent_label: str
    status: str
    description: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[str] = None


class WorkflowState(BaseModel):
    id: str
    task_id: str
    status: str
    steps: list[AgentStep]
    created_at: str
