from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from app.agent import SecurityAgent
from app.auth import approval_key_valid, validate_runtime_settings, verify_api_key
from app.config import get_settings
from app.db import Database
from app.llm import LLMClient
from app.policy import PolicyEngine
from app.rag import discover_documents
from app.schemas import InvestigationRequest, InvestigationResponse
from app.web import create_web_router

def create_app() -> FastAPI:
    settings = get_settings()
    validate_runtime_settings(settings)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.data_dir / "security-agent.db")
    policy = PolicyEngine(settings.policy_file, settings.lab_cidrs)
    agent = SecurityAgent(LLMClient(settings), db, policy, settings.skill_dir)

    app = FastAPI(
        title=settings.app_name,
        version="0.3.0",
        docs_url="/docs" if settings.enable_api_docs else None,
        redoc_url="/redoc" if settings.enable_api_docs else None,
        openapi_url="/openapi.json" if settings.enable_api_docs else None,
    )
    app.state.db = db
    app.state.agent = agent

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

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
        source_dirs = [
            Path(item.strip())
            for item in settings.knowledge_dirs.split(",")
            if item.strip()
        ]
        document_count, chunk_count = app.state.db.rebuild_knowledge(
            (
                [
                    {
                        "source": chunk.source,
                        "title": chunk.title,
                        "content": chunk.content,
                    }
                    for chunk in document.chunks
                ]
                for document in discover_documents(
                    source_dirs,
                    max_documents=settings.rag_max_documents,
                    max_file_bytes=settings.rag_max_file_bytes,
                    chunk_chars=settings.rag_chunk_chars,
                    overlap_chars=settings.rag_overlap_chars,
                )
            )
        )
        return {"documents": document_count, "chunks": chunk_count}

    assets = settings.web_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    app.include_router(create_web_router(db, agent, settings))

    return app


app = create_app()
