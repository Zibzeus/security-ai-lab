import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.config import Settings


COOKIE_NAME = "security_ai_session"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    selected_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=selected_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
        maxmem=64 * 1024 * 1024,
    )
    return "$".join(
        [
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            _b64_encode(selected_salt),
            _b64_encode(digest),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64_decode(expected)),
            maxmem=64 * 1024 * 1024,
        )
        return hmac.compare_digest(actual, _b64_decode(expected))
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class WebSession:
    username: str
    csrf_token: str
    expires_at: int


def create_session_token(username: str, settings: Settings) -> tuple[str, WebSession]:
    session = WebSession(
        username=username,
        csrf_token=secrets.token_urlsafe(24),
        expires_at=int(time.time()) + settings.web_session_ttl_seconds,
    )
    payload = _b64_encode(
        json.dumps(
            {
                "username": session.username,
                "csrf": session.csrf_token,
                "exp": session.expires_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = hmac.new(
        settings.web_session_secret.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload}.{_b64_encode(signature)}", session


def parse_session_token(token: str, settings: Settings) -> WebSession | None:
    try:
        payload, signature = token.split(".", 1)
        expected = hmac.new(
            settings.web_session_secret.encode("utf-8"),
            payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64_decode(signature)):
            return None
        value = json.loads(_b64_decode(payload))
        session = WebSession(
            username=str(value["username"]),
            csrf_token=str(value["csrf"]),
            expires_at=int(value["exp"]),
        )
        if session.expires_at < int(time.time()):
            return None
        if session.username != settings.web_username:
            return None
        return session
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def require_session(request: Request, settings: Settings) -> WebSession:
    token = request.cookies.get(COOKIE_NAME, "")
    session = parse_session_token(token, settings)
    if session is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return session


def require_csrf(request: Request, settings: Settings) -> WebSession:
    session = require_session(request, settings)
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return session
