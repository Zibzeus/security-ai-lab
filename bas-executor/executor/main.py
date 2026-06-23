from fastapi import Depends, FastAPI, HTTPException

from executor.auth import verify_signature
from executor.config import get_settings, validate_runtime_settings
from executor.models import ExecutionRequest, ExecutionResponse
from executor.runtime import run_request


settings = get_settings()
validate_runtime_settings(settings)
app = FastAPI(title="BAS Executor", version="0.2.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/v1/execute",
    response_model=ExecutionResponse,
    dependencies=[Depends(verify_signature)],
)
async def execute(request: ExecutionRequest) -> ExecutionResponse:
    try:
        return await run_request(request, get_settings())
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
