from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Task(BaseModel):
    id: str
    title: str
    description: str
    tags: list[str]
    status: str
    created_at: str
    updated_at: str


class CreateTaskInput(BaseModel):
    title: str
    description: str
    tags: list[str] = []
