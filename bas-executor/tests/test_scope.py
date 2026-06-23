from pathlib import Path

import pytest

from executor.scope import Engagement, validate_targets


def test_scope() -> None:
    engagement = Engagement.load(
        Path(__file__).parents[1] / "engagements" / "active.example.yaml"
    )
    engagement.validate_target("10.100.31.209")
    engagement.validate_target("10.100.31.0/28")
    engagement.validate_target("dc.cs.lab")
    with pytest.raises(ValueError):
        engagement.validate_target("8.8.8.8")
    with pytest.raises(ValueError):
        engagement.validate_target("8.8.8.0/24")


def test_category_policy_and_nested_targets() -> None:
    engagement = Engagement.load(
        Path(__file__).parents[1] / "engagements" / "active.example.yaml"
    )
    assert engagement.category_action("active_scan") == "allow"
    assert engagement.category_action("remote_execution") == "approval"
    assert engagement.category_action("destructive") == "deny"
    assert engagement.category_action("unregistered") == "deny"
    validate_targets(
        engagement,
        {"nested": {"destination_ip": "10.100.31.10"}},
    )
    with pytest.raises(ValueError):
        validate_targets(
            engagement,
            {"nested": {"destination_ip": "8.8.8.8"}},
        )
