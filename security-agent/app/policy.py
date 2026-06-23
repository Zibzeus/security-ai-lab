import ipaddress
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.schemas import Profile, Risk


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str


class PolicyEngine:
    def __init__(self, path: Path, lab_cidrs: str):
        self.rules = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.networks = [
            ipaddress.ip_network(value.strip())
            for value in lab_cidrs.split(",")
            if value.strip()
        ]

    def decide(self, profile: Profile, risk: Risk) -> Decision:
        action = self.rules["profiles"][profile.value].get(
            risk.value, self.rules["defaults"][risk.value]
        )
        reasons = {
            "allow": "Allowed by profile policy",
            "dry_run": "Simulation only; no target-side mutation is permitted",
            "approval": "A human approval is required before execution",
            "deny": "Denied by policy",
        }
        return Decision(action=action, reason=reasons[action])

    def target_is_in_lab(self, target: str) -> bool:
        try:
            address = ipaddress.ip_address(target)
        except ValueError:
            return False
        return any(address in network for network in self.networks)
