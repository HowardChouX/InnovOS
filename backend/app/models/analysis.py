from pydantic import BaseModel


class ConflictNode(BaseModel):
    id: str
    label: str
    description: str
    type: str
    color: Optional[str] = None


class ConflictEdge(BaseModel):
    source_id: str
    target_id: str
    label: str


class ConflictAnalysis(BaseModel):
    id: str
    task_id: str
    center_node: ConflictNode
    satellite_nodes: list[ConflictNode]
    edges: list[ConflictEdge]
    triz_principles: list[str]
