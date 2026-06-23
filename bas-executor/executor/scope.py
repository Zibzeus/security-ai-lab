import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Engagement:
    engagement_id: str
    active: bool
    networks: list[Any]
    domains: list[str]
    automatic_categories: list[str]
    approval_categories: list[str]
    denied_categories: list[str]
    caldera_groups: list[str]
    caldera_adversaries: list[str]

    @classmethod
    def load(cls, path: Path) -> "Engagement":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            engagement_id=raw["engagement_id"],
            active=bool(raw["active"]),
            networks=[ipaddress.ip_network(item) for item in raw["scope"]["cidrs"]],
            domains=[item.lower() for item in raw["scope"].get("domains", [])],
            automatic_categories=raw["policy"].get("automatic_categories", []),
            approval_categories=raw["policy"].get("approval_categories", []),
            denied_categories=raw["policy"].get("denied_categories", []),
            caldera_groups=raw["scope"].get("caldera_groups", []),
            caldera_adversaries=raw["scope"].get("caldera_adversaries", []),
        )

    def validate_target(self, value: str) -> None:
        if "/" in value:
            try:
                network = ipaddress.ip_network(value, strict=False)
            except ValueError as exc:
                raise ValueError("Target network is invalid") from exc
            if not any(network.subnet_of(allowed) for allowed in self.networks):
                raise ValueError("Target network is outside engagement scope")
            return
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            hostname = value.rstrip(".").lower()
            if not any(
                hostname == domain or hostname.endswith(f".{domain}")
                for domain in self.domains
            ):
                raise ValueError("Target hostname is outside engagement scope")
            return
        if not any(address in network for network in self.networks):
            raise ValueError("Target IP is outside engagement scope")

    def category_action(self, category: str) -> str:
        if category in self.denied_categories:
            return "deny"
        if category in self.automatic_categories:
            return "allow"
        if category in self.approval_categories:
            return "approval"
        return "deny"


def validate_targets(engagement: Engagement, arguments: dict[str, Any]) -> None:
    target_keys = {
        "target",
        "targets",
        "dc_ip",
        "host",
        "hostname",
        "source_ip",
        "destination_ip",
    }

    def walk(value: Any, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, key.lower())
        elif isinstance(value, list):
            for item in value:
                walk(item, parent_key)
        elif parent_key in target_keys:
            engagement.validate_target(str(value))

    walk(arguments)
