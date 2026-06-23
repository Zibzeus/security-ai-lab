from typing import Any

from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    capability: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    case_id: str = Field(min_length=3, max_length=100)
    approved: bool = False


class ExecutionResponse(BaseModel):
    capability: str
    status: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    artifact_dir: str | None = None
