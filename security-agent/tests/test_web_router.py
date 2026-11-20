from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.web import create_web_router
from app.web_auth import hash_password


class DummyAgent:
    pass


def test_web_login_csrf_and_case_creation(tmp_path) -> None:
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<h1>Security AI</h1>", encoding="utf-8")
    settings = Settings(
        web_username="operator",
        web_password_hash=hash_password(
            "correct horse battery staple",
            salt=b"0123456789abcdef",
        ),
        web_session_secret="s" * 32,
        approval_key="p" * 32,
        web_secure_cookie=False,
        web_dir=web_dir,
    )
    db = Database(tmp_path / "agent.db")
    app = FastAPI()
    app.include_router(create_web_router(db, DummyAgent(), settings))  # type: ignore[arg-type]
    client = TestClient(app)

    assert client.get("/api/web/session").status_code == 401
    login = client.post(
        "/api/web/login",
        json={
            "username": "operator",
            "password": "correct horse battery staple",
        },
    )
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]

    assert client.post(
        "/api/web/cases",
        json={"profile": "soc", "title": "Missing CSRF"},
    ).status_code == 403

    created = client.post(
        "/api/web/cases",
        headers={"X-CSRF-Token": csrf},
        json={"profile": "soc", "title": "Kerberos triage"},
    )
    assert created.status_code == 200
    case_id = created.json()["id"]
    detail = client.get(f"/api/web/cases/{case_id}")
    assert detail.status_code == 200
    assert detail.json()["profile"] == "soc"

    db.create_approval(
        "approval-1",
        case_id,
        "shell.execute",
        {
            "capability": "shell.execute",
            "arguments": {"command": "id", "targets": ["10.100.31.5"]},
        },
        "Remote execution requires approval",
    )
    denied = client.post(
        "/api/web/approvals/approval-1/approve",
        headers={"X-CSRF-Token": csrf},
        json={"approval_key": "wrong"},
    )
    assert denied.status_code == 403
    assert db.get_approval("approval-1")["status"] == "pending"
