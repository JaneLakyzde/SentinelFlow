"""Load the versioned API-security review Skill."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SkillBundle:
    """Trusted, versioned instructions supplied to the reviewer."""

    name: str
    version: str
    instructions: str
    references: tuple[tuple[str, str], ...]


def default_skill_path() -> Path:
    """Resolve the bundled Skill in an installed wheel or source checkout."""
    package_path = (
        Path(__file__).resolve().parents[1] / "resources" / "skills" / "audit-api-security"
    )
    repository_path = (
        Path(__file__).resolve().parents[2]
        / "domains"
        / "api_security"
        / "skills"
        / "audit-api-security"
    )
    if package_path.is_dir():
        return package_path
    if repository_path.is_dir():
        return repository_path
    raise FileNotFoundError("bundled audit-api-security Skill was not found")


def load_skill_bundle(path: Path | str) -> SkillBundle:
    """Load the required Skill files without interpreting event data."""
    skill_path = Path(path)
    instructions_path = skill_path / "SKILL.md"
    version_path = skill_path / "VERSION"
    instructions = instructions_path.read_text(encoding="utf-8")
    version = version_path.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError("Skill VERSION must be non-empty")
    name = _frontmatter_name(instructions)
    reference_path = skill_path / "references" / "parameter-enumeration.md"
    reference = reference_path.read_text(encoding="utf-8")
    return SkillBundle(
        name=name,
        version=version,
        instructions=instructions,
        references=(("parameter-enumeration.md", reference),),
    )


def _frontmatter_name(instructions: str) -> str:
    lines = instructions.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("Skill must start with YAML frontmatter")
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("name:"):
            name = line.removeprefix("name:").strip()
            if name:
                return name
    raise ValueError("Skill frontmatter must contain a non-empty name")
