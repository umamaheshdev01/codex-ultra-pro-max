from dataclasses import dataclass, field
from pathlib import Path

import yaml


BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent
USER_SKILLS_DIR = Path.home() / ".codex" / "skills"


@dataclass
class Skill:
    name: str
    description: str
    icon: str
    system_prompt: str
    temperature: float = 0.3
    tools_allowed: list[str] = field(default_factory=list)


SkillMeta = Skill


class SkillRegistry:
    def __init__(
        self,
        builtin_dir: Path = BUILTIN_SKILLS_DIR,
        user_dir: Path = USER_SKILLS_DIR,
    ):
        self.builtin_dir = builtin_dir
        self.user_dir = user_dir
        self.skills: dict[str, Skill] = {}
        self._load_dir(self.builtin_dir)
        self._load_dir(self.user_dir)

    def list(self) -> list[SkillMeta]:
        return sorted(self.skills.values(), key=lambda skill: skill.name)

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def _load_dir(self, skills_dir: Path):
        if not skills_dir.exists():
            return

        for path in sorted(skills_dir.glob("*.yaml")):
            skill = self._load_skill(path)
            self.skills[skill.name] = skill

    def _load_skill(self, path: Path) -> Skill:
        with path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        return Skill(
            name=str(raw["name"]),
            description=str(raw.get("description", "")),
            icon=str(raw.get("icon", "")),
            system_prompt=str(raw["system_prompt"]),
            temperature=float(raw.get("temperature", 0.3)),
            tools_allowed=list(raw.get("tools_allowed") or []),
        )
