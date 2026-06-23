import asyncio
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agent import SecurityAgent
from app.auth import approval_key_valid
from app.config import Settings
from app.db import Database
from app.mcp_bridge import MCPBridge
from app.schemas import ConversationTurn, InvestigationRequest, Profile, ToolRequest
from app.web_auth import (
    COOKIE_NAME,
    create_session_token,
    require_csrf,
    require_session,
    verify_password,
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class CaseCreateRequest(BaseModel):
    profile: Profile
    title: str = Field(default="New investigation", min_length=1, max_length=160)


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    evidence: list[str] = Field(default_factory=list, max_length=100)
    allow_tools: bool = True


class ApprovalRequest(BaseModel):
    approval_key: str = Field(min_length=1, max_length=1024)


class LoginLimiter:
    def __init__(self, attempts: int = 5, window_seconds: int = 300):
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, client: str) -> None:
        now = time.monotonic()
        recent = [
            value
            for value in self._attempts[client]
            if now - value < self.window_seconds
        ]
        self._attempts[client] = recent
        if len(recent) >= self.attempts:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Try again later.",
            )

    def failure(self, client: str) -> None:
        self._attempts[client].append(time.monotonic())

    def success(self, client: str) -> None:
        self._attempts.pop(client, None)


def _client_address(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _case_or_404(db: Database, case_id: str) -> dict[str, Any]:
    case = db.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _llm_health_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, "/health", "", ""))


async def _http_status(name: str, url: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        return {
            "name": name,
            "status": "online",
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "offline",
            "error": str(exc)[:240],
        }


async def _mcp_status(
    bridge: MCPBridge, server_name: str
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = await asyncio.wait_for(
            bridge.list_tools(server_name), timeout=12.0
        )
        return {
            "name": server_name,
            "status": "online",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "tool_count": len(result.get("tools", [])),
        }
    except Exception as exc:
        return {
            "name": server_name,
            "status": "offline",
            "error": str(exc)[:240],
        }


def create_web_router(
    db: Database,
    agent: SecurityAgent,
    settings: Settings,
) -> APIRouter:
    router = APIRouter()
    limiter = LoginLimiter()

    @router.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        path = settings.web_dir / "index.html"
        if not path.is_file():
            raise HTTPException(status_code=503, detail="Web UI is not installed")
        return FileResponse(path)

    @router.post("/api/web/login")
    async def login(
        body: LoginRequest, request: Request, response: Response
    ) -> dict[str, Any]:
        client = _client_address(request)
        limiter.check(client)
        username_ok = body.username == settings.web_username
        password_ok = verify_password(body.password, settings.web_password_hash)
        if not username_ok or not password_ok:
            limiter.failure(client)
            db.audit(
                "_system",
                "web_login_failed",
                {"client": client, "username": body.username[:128]},
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")
        limiter.success(client)
        token, session = create_session_token(body.username, settings)
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=settings.web_session_ttl_seconds,
            httponly=True,
            secure=settings.web_secure_cookie,
            samesite="strict",
            path="/",
        )
        db.audit(
            "_system",
            "web_login_succeeded",
            {"client": client, "username": body.username},
        )
        return {
            "authenticated": True,
            "username": session.username,
            "csrf_token": session.csrf_token,
            "expires_at": session.expires_at,
        }

    @router.post("/api/web/logout")
    async def logout(request: Request, response: Response) -> dict[str, bool]:
        session = require_csrf(request, settings)
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            secure=settings.web_secure_cookie,
            httponly=True,
            samesite="strict",
        )
        db.audit(
            "_system",
            "web_logout",
            {"username": session.username, "client": _client_address(request)},
        )
        return {"authenticated": False}

    @router.get("/api/web/session")
    async def session(request: Request) -> dict[str, Any]:
        current = require_session(request, settings)
        return {
            "authenticated": True,
            "username": current.username,
            "csrf_token": current.csrf_token,
            "expires_at": current.expires_at,
        }

    @router.get("/api/web/cases")
    async def list_cases(request: Request) -> list[dict[str, Any]]:
        require_session(request, settings)
        return db.list_cases()

    @router.post("/api/web/cases")
    async def create_case(
        body: CaseCreateRequest, request: Request
    ) -> dict[str, Any]:
        require_csrf(request, settings)
        case_id = str(uuid.uuid4())
        case = db.create_case(case_id, body.profile.value, body.title.strip())
        db.audit(
            case_id,
            "web_case_created",
            {"profile": body.profile.value, "title": body.title.strip()},
        )
        return case

    @router.get("/api/web/cases/{case_id}")
    async def get_case(case_id: str, request: Request) -> dict[str, Any]:
        require_session(request, settings)
        case = _case_or_404(db, case_id)
        return {
            **case,
            "messages": db.list_messages(case_id),
            "approvals": db.list_approvals(case_id),
        }

    @router.post("/api/web/cases/{case_id}/messages")
    async def send_message(
        case_id: str, body: ChatRequest, request: Request
    ) -> dict[str, Any]:
        require_csrf(request, settings)
        case = _case_or_404(db, case_id)
        history = [
            ConversationTurn.model_validate(item)
            for item in db.recent_conversation(
                case_id,
                settings.web_memory_turns,
                settings.web_memory_chars_per_turn,
            )
        ]
        db.add_message(
            case_id,
            "user",
            body.message,
            evidence=body.evidence,
        )
        investigation = await agent.investigate(
            InvestigationRequest(
                profile=Profile(case["profile"]),
                objective=body.message,
                evidence=body.evidence,
                case_id=case_id,
                allow_tools=body.allow_tools,
                conversation_history=history,
            )
        )
        tool_results = [
            result.model_dump(mode="json")
            for result in investigation.tool_results
        ]
        message = db.add_message(
            case_id,
            "assistant",
            investigation.report,
            tool_results=tool_results,
            citations=investigation.citations,
        )
        approvals: list[dict[str, Any]] = []
        for result in investigation.tool_results:
            if result.name != "bas_execute" or result.status != "pending_approval":
                continue
            capability = str(result.arguments.get("capability", ""))
            if not capability:
                continue
            approvals.append(
                db.create_approval(
                    str(uuid.uuid4()),
                    case_id,
                    capability,
                    result.arguments,
                    result.justification,
                )
            )
        return {
            "message": message,
            "approvals": approvals,
            "case": db.get_case(case_id),
        }

    @router.post("/api/web/approvals/{approval_id}/approve")
    async def approve(
        approval_id: str,
        body: ApprovalRequest,
        request: Request,
    ) -> dict[str, Any]:
        session = require_csrf(request, settings)
        if not approval_key_valid(body.approval_key, settings):
            db.audit(
                "_system",
                "web_approval_credential_failed",
                {
                    "approval_id": approval_id,
                    "operator": session.username,
                    "client": _client_address(request),
                },
            )
            raise HTTPException(
                status_code=403,
                detail="Invalid approval credential",
            )
        approval = db.claim_approval(approval_id)
        if approval is None:
            raise HTTPException(
                status_code=409,
                detail="Approval is missing or no longer pending",
            )
        case = _case_or_404(db, str(approval["case_id"]))
        tool_request = ToolRequest(
            name="bas_execute",
            arguments=dict(approval["arguments"]),
            justification=str(approval["justification"]),
        )
        try:
            result = await agent.execute_approved_tool(
                str(approval["case_id"]),
                Profile(case["profile"]),
                tool_request,
            )
        except Exception:
            db.set_approval_status(approval_id, "error")
            raise
        final_status = (
            "approved"
            if result.status in {"success", "simulated"}
            else result.status
        )
        db.set_approval_status(approval_id, final_status)
        db.audit(
            str(approval["case_id"]),
            "web_action_approved",
            {
                "approval_id": approval_id,
                "capability": approval["capability"],
                "operator": session.username,
                "result": result.status,
            },
        )
        message = db.add_message(
            str(approval["case_id"]),
            "assistant",
            (
                f"Approved execution `{approval['capability']}` completed "
                f"with status `{result.status}`."
            ),
            tool_results=[result.model_dump(mode="json")],
        )
        return {
            "approval": db.get_approval(approval_id),
            "message": message,
        }

    @router.post("/api/web/approvals/{approval_id}/reject")
    async def reject(approval_id: str, request: Request) -> dict[str, Any]:
        session = require_csrf(request, settings)
        approval = db.get_approval(approval_id)
        if approval is None or approval["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="Approval is missing or no longer pending",
            )
        db.set_approval_status(approval_id, "rejected")
        db.audit(
            str(approval["case_id"]),
            "web_action_rejected",
            {
                "approval_id": approval_id,
                "capability": approval["capability"],
                "operator": session.username,
            },
        )
        message = db.add_message(
            str(approval["case_id"]),
            "assistant",
            f"Pending action `{approval['capability']}` was rejected.",
        )
        return {
            "approval": db.get_approval(approval_id),
            "message": message,
        }

    @router.get("/api/web/audit")
    async def audit(
        request: Request,
        case_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        require_session(request, settings)
        return db.list_audit(case_id=case_id, limit=min(max(limit, 1), 200))

    @router.get("/api/web/status")
    async def status(request: Request) -> dict[str, Any]:
        require_session(request, settings)
        bridge = MCPBridge(settings.mcp_config_file)
        checks = await asyncio.gather(
            _http_status("llm", _llm_health_url(settings.llm_base_url)),
            _http_status(
                "bas",
                f"{settings.bas_executor_url.rstrip('/')}/health",
            ),
            _mcp_status(bridge, "extrahop"),
            _mcp_status(bridge, "crowdstrike"),
        )
        return {"services": {item["name"]: item for item in checks}}

    return router
