import secrets

from fastapi import Header, HTTPException

from app.config import Settings, get_settings


PLACEHOLDER_PREFIXES = ("change-me", "replace-", "development-")


def _strong_secret(value: str) -> bool:
    return len(value) >= 32 and not value.lower().startswith(PLACEHOLDER_PREFIXES)


def validate_runtime_settings(settings: Settings) -> None:
    required = {
        "API_KEY": settings.api_key,
        "APPROVAL_KEY": settings.approval_key,
        "BAS_EXECUTOR_SECRET": settings.bas_executor_secret,
        "WEB_SESSION_SECRET": settings.web_session_secret,
    }
    invalid = [name for name, value in required.items() if not _strong_secret(value)]
    if invalid:
        raise ValueError(
            f"Set non-placeholder 32+ character secrets for: {', '.join(invalid)}"
        )
    if not settings.web_username.strip():
        raise ValueError("WEB_USERNAME must not be empty")
    if not settings.web_password_hash.startswith("scrypt$"):
        raise ValueError(
            "Set WEB_PASSWORD_HASH using scripts/hash_web_password.py"
        )


def verify_api_key(x_api_key: str = Header(default="")) -> None:
    configured = get_settings().api_key
    if not configured or not secrets.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="Invalid API key")


def approval_key_valid(supplied: str, settings: Settings) -> bool:
    return bool(
        settings.approval_key
        and supplied
        and secrets.compare_digest(supplied, settings.approval_key)
    )
