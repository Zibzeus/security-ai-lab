from dataclasses import dataclass
from pathlib import Path

import yaml

from app.schemas import Profile


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    profiles: list[str]
    content: str


class SkillRegistry:
    def __init__(self, root: Path):
        self.root = root

    def all(self) -> list[Skill]:
        skills: list[Skill] = []
        for manifest_path in sorted(self.root.glob("*/manifest.yaml")):
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            skills.append(
                Skill(
                    name=manifest["name"],
                    description=manifest["description"],
                    profiles=manifest["profiles"],
                    content=(manifest_path.parent / "SKILL.md").read_text(
                        encoding="utf-8"
                    ),
                )
            )
        return skills

    def catalog(self, profile: Profile) -> list[dict[str, str]]:
        return [
            {"name": skill.name, "description": skill.description}
            for skill in self.all()
            if profile.value in skill.profiles
        ]

    def select(self, profile: Profile, objective: str) -> list[Skill]:
        words = set(objective.lower().replace("-", " ").split())
        ranked: list[tuple[int, Skill]] = []
        for skill in self.all():
            if profile.value not in skill.profiles:
                continue
            haystack = f"{skill.name} {skill.description}".lower().replace("-", " ")
            score = sum(1 for word in words if len(word) > 3 and word in haystack)
            ranked.append((score, skill))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [skill for score, skill in ranked[:2] if score > 0]
