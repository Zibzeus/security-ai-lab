from pathlib import Path

from app.policy import PolicyEngine
from app.schemas import Profile, Risk


POLICY = Path(__file__).parents[1] / "policies" / "default.yaml"


def test_soc_write_requires_approval() -> None:
    engine = PolicyEngine(POLICY, "10.0.0.0/8")
    assert engine.decide(Profile.SOC, Risk.WRITE).action == "approval"


def test_destructive_is_denied() -> None:
    engine = PolicyEngine(POLICY, "10.0.0.0/8")
    assert engine.decide(Profile.REDTEAM, Risk.DESTRUCTIVE).action == "deny"


def test_target_scope() -> None:
    engine = PolicyEngine(POLICY, "10.0.0.0/8,192.168.0.0/16")
    assert engine.target_is_in_lab("10.100.31.121")
    assert not engine.target_is_in_lab("8.8.8.8")
