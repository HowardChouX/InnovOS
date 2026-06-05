from pydantic import BaseModel
from typing import Optional


class Patent(BaseModel):
    id: str
    title: str
    abstract: str
    applicants: list[str]
    inventors: list[str]
    filing_date: str
    publication_date: str
    patent_number: str
    ipc_codes: list[str]
    relevance_score: int


class PatentStats(BaseModel):
    total_count: int
    related_count: int
    core_count: int
    analyzed_count: int
    top_patents: list[Patent]
