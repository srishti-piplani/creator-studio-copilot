"""JSON-serializable state persisted per LangGraph thread."""
from typing import Literal, TypedDict
from pydantic import BaseModel, Field

Intent = Literal['learn', 'troubleshoot', 'discover', 'clarify']

class Route(BaseModel):
    intent: Intent
    goal: str = Field(max_length=4000)
    equipment: list[str] = Field(default_factory=list, max_length=12)
    software_specific: bool = False
    version: str | None = Field(default=None, description='Software version stated by user only, not hardware generation or supported documentation version')
    outcome: Literal['unknown', 'failed', 'resolved'] = 'unknown'
    new_goal: bool = False

class AgentState(TypedDict, total=False):
    session_id: str
    messages: list[dict]
    intent: str
    equipment: list[str]
    goal: str
    version: str | None
    software_specific: bool
    questions_asked: list[str]
    steps: list[dict]
    evidence: list[dict]
    citations: list[dict]
    web_history: list[dict]
    evaluation: dict
    response: dict
    status: str
    error: str | None
    web_attempted: bool
    route_outcome: str

    activities: list[dict]
    how_to: bool
    new_topic: bool

    primary_software: str | None

    answer_checks: list[dict]

    creative_goal: bool
    resource_checks: list[dict]
