from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException

from app.agent import SecurityAgent
from app.auth import approval_key_valid, validate_runtime_settings, verify_api_key
from app.config import get_settings
from app.db import Database
from app.llm import LLMClient
from app.policy import PolicyEngine
from app.schemas import InvestigationRequest, InvestigationResponse

def create_app() -> FastAPI:
    settings = get_settings()
    validate_runtime_settings(settings)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.data_dir / "security-agent.db")
    policy = PolicyEngine(settings.policy_file, settings.lab_cidrs)
    agent = SecurityAgent(LLMClient(settings), db, policy, settings.skill_dir)

    app = FastAPI(title=settings.app_name, version="0.2.0")
    app.state.db = db
    app.state.agent = agent

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/investigate",
        response_model=InvestigationResponse,
        dependencies=[Depends(verify_api_key)],
    )
    async def investigate(
        request: InvestigationRequest,
        x_approval_key: str = Header(default=""),
    ) -> InvestigationResponse:
        if request.approved_capabilities and not approval_key_valid(
            x_approval_key, settings
        ):
            raise HTTPException(
                status_code=403,
                detail="A valid X-Approval-Key is required for approved capabilities",
            )
        return await app.state.agent.investigate(request)

    @app.post("/v1/knowledge/reindex", dependencies=[Depends(verify_api_key)])
    async def reindex() -> dict[str, int]:
        count = 0
        source_dirs = [
            Path(item.strip())
            for item in settings.knowledge_dirs.split(",")
            if item.strip()
        ]
        for source_dir in source_dirs:
            for path in source_dir.glob("*.md"):
                app.state.db.index_document(
                    source=f"{source_dir.name}/{path.name}",
                    title=path.stem.replace("-", " ").title(),
                    content=path.read_text(encoding="utf-8"),
                )
                count += 1
        return {"indexed": count}

    return app


app = create_app()
