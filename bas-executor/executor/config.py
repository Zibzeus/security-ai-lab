from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    executor_secret: str = ""
    engagement_file: Path = Path("/opt/bas-executor/engagements/active.yaml")
    credential_file: Path = Path("/opt/bas-executor/secrets/credentials.yaml")
    artifact_dir: Path = Path("/var/lib/bas-executor/artifacts")
    caldera_url: str = "http://127.0.0.1:8888"
    caldera_api_key: str = ""
    bloodhound_url: str = "http://127.0.0.1:8080"
    bloodhound_token_id: str = ""
    bloodhound_token_key: str = ""
    bubblewrap_path: Path = Path("/usr/bin/bwrap")
    shell_path: Path = Path("/bin/bash")
    shell_readonly_binds: str = (
        "/usr,/bin,/lib,/lib64,/etc/resolv.conf,/etc/hosts,"
        "/etc/nsswitch.conf,/etc/ssl/certs,/etc/passwd,/etc/group"
    )
    max_shell_command_chars: int = 12_000
    max_output_bytes: int = 1_000_000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def validate_runtime_settings(settings: Settings) -> None:
    if len(settings.executor_secret) < 32 or settings.executor_secret.startswith(
        ("change-me", "replace-")
    ):
        raise ValueError("EXECUTOR_SECRET must be a non-placeholder value of 32+ chars")


@lru_cache
def get_settings() -> Settings:
    return Settings()
