#!/usr/bin/env python3
from getpass import getpass
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.web_auth import normalize_password_hash, verify_password  # noqa: E402


def main() -> None:
    settings = get_settings()
    encoded = normalize_password_hash(settings.web_password_hash)
    print(f"configured_username={settings.web_username}")
    print(f"password_hash_configured={encoded.startswith('scrypt$')}")
    print(f"password_hash_length={len(encoded)}")
    password = getpass("Web UI password to verify: ")
    print(f"password_ok={verify_password(password, encoded)}")


if __name__ == "__main__":
    main()
