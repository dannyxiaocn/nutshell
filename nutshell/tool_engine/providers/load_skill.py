from pathlib import Path


async def load_skill(
    *,
    name: str,
    _agent: object | None = None,
) -> str:
    """Load the full content of a named skill.

    Call this when you identify that a skill is relevant to the current task.
    Returns the complete skill documentation so you can follow its instructions.

    Args:
        name: The skill name as shown in the available_skills catalog.
    """
    skills = getattr(_agent, "skills", []) or []
    for skill in skills:
        if skill.name == name:
            if skill.location is not None:
                from nutshell.skill_engine.loader import _parse_frontmatter
                text = Path(skill.location).read_text(encoding="utf-8")
                _, body = _parse_frontmatter(text)
                return body.strip() or f"(skill '{name}' has no body)"
            return skill.body.strip() or f"(skill '{name}' has no body)"
    available = [s.name for s in skills]
    return f"Skill '{name}' not found. Available: {available}"
