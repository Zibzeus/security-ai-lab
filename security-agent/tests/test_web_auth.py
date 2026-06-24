from app.config import Settings
from app.web_auth import (
    create_session_token,
    hash_password,
    normalize_password_hash,
    parse_session_token,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password(
        "correct horse battery staple",
        salt=b"0123456789abcdef",
    )
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("incorrect password", encoded)
    assert verify_password("correct horse battery staple", f" '{encoded}' \n")
    assert "correct horse" not in encoded
    assert normalize_password_hash(f" '{encoded}' \n") == encoded


def test_signed_session_round_trip() -> None:
    settings = Settings(
        web_username="operator",
        web_session_secret="s" * 32,
    )
    token, created = create_session_token("operator", settings)
    parsed = parse_session_token(token, settings)
    assert parsed == created

    modified = f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}"
    assert parse_session_token(modified, settings) is None
