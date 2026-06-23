from app.auth import approval_key_valid, validate_runtime_settings
from app.config import Settings


def test_runtime_secrets_reject_placeholders() -> None:
    settings = Settings(
        api_key="change-me",
        approval_key="replace-with-key",
        bas_executor_secret="short",
    )
    try:
        validate_runtime_settings(settings)
    except ValueError as exc:
        assert "API_KEY" in str(exc)
        assert "APPROVAL_KEY" in str(exc)
        assert "BAS_EXECUTOR_SECRET" in str(exc)
    else:
        raise AssertionError("placeholder secrets were accepted")


def test_approval_key_is_separate() -> None:
    settings = Settings(
        api_key="a" * 32,
        approval_key="b" * 32,
        bas_executor_secret="c" * 32,
    )
    validate_runtime_settings(settings)
    assert approval_key_valid("b" * 32, settings)
    assert not approval_key_valid("a" * 32, settings)
