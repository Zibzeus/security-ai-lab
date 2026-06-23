import hashlib
import hmac
import time
from collections import deque

from fastapi import Header, HTTPException, Request

from executor.config import get_settings


NONCES: deque[str] = deque(maxlen=10_000)


async def verify_signature(
    request: Request,
    x_bas_timestamp: str = Header(default=""),
    x_bas_nonce: str = Header(default=""),
    x_bas_signature: str = Header(default=""),
) -> None:
    try:
        timestamp = int(x_bas_timestamp)
    except ValueError as exc:
        raise HTTPException(401, "Invalid timestamp") from exc
    if abs(int(time.time()) - timestamp) > 60:
        raise HTTPException(401, "Expired request")
    if not x_bas_nonce or x_bas_nonce in NONCES:
        raise HTTPException(401, "Invalid or replayed nonce")
    body = await request.body()
    expected = hmac.new(
        get_settings().executor_secret.encode(),
        x_bas_timestamp.encode() + b"." + x_bas_nonce.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_bas_signature):
        raise HTTPException(401, "Invalid signature")
    NONCES.append(x_bas_nonce)
