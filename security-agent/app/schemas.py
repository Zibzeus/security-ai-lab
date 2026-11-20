from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Profile(StrEnum):
    SOC = "soc"
    REDTEAM = "redteam"
    GRC = "grc"


class Risk(StrEnum):
    READ = "read"
    ACTIVE = "active"
    SIMULATE = "simulate"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class InvestigationRequest(BaseModel):
    profile: Profile
    objective: str = Field(min_length=3, max_length=4000)
    evidence: list[str] = Field(default_factory=list, max_length=100)
    case_id: str | None = Field(default=None, max_length=100)
    allow_tools: bool = True
    approved_capabilities: list[str] = Field(default_factory=list, max_length=50)
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list, max_length=24
    )


class ToolRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    justification: str = ""


class Plan(BaseModel):
    summary: str
    hypotheses: list[str] = Field(default_factory=list)
    tool_requests: list[ToolRequest] = Field(default_factory=list)


class ToolResult(BaseModel):
    name: str
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    justification: str = ""


class InvestigationResponse(BaseModel):
    case_id: str
    profile: Profile
    status: str
    report: str
    citations: list[str] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
