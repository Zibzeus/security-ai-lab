from enum import StrEnum
from typing import Any

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


class InvestigationRequest(BaseModel):
    profile: Profile
    objective: str = Field(min_length=3, max_length=4000)
    evidence: list[str] = Field(default_factory=list, max_length=100)
    case_id: str | None = Field(default=None, max_length=100)
    allow_tools: bool = True
    approved_capabilities: list[str] = Field(default_factory=list, max_length=50)


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


class InvestigationResponse(BaseModel):
    case_id: str
    profile: Profile
    status: str
    report: str
    citations: list[str] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
