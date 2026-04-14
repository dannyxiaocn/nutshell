from __future__ import annotations
from html import escape
from butterfly.core.skill import Skill


def build_skills_block(skills: list[Skill]) -> str:
    """Render a list of skills into a system prompt block.

    File-backed skills (with a ``location``) get a catalog entry for
    progressive disclosure — the model reads SKILL.md on demand via its
    file/bash tool.  Inline skills (no location) have their body injected
    directly into the system prompt.

    Returns an empty string when there are no skills.
    """
    if not skills:
        return ""

    parts: list[str] = []

    # File-backed skills → progressive disclosure via the built-in skill tool.
    file_skills = [s for s in skills if s.location is not None]
    if file_skills:
        catalog = ["<available_skills>"]
        for s in file_skills:
            safe_name = escape(s.name)
            safe_description = escape(s.description)
            safe_when_to_use = escape(s.when_to_use) if s.when_to_use else ""
            when_to_use = f"\n    <when_to_use>{safe_when_to_use}</when_to_use>" if safe_when_to_use else ""
            catalog.append(
                f"  <skill>\n"
                f"    <name>{safe_name}</name>\n"
                f"    <description>{safe_description}</description>\n"
                f"{when_to_use}"
                f"  </skill>"
            )
        catalog.append("</available_skills>")
        parts.append(
            "\n\n# Available Skills\n"
            "Use the `skill` tool to load a skill before proceeding whenever a task matches "
            "a listed skill's description.\n"
            "This is a blocking requirement: do not proceed with matching work until the "
            "relevant skill has been loaded.\n\n"
            + "\n".join(catalog)
        )

    # Inline skills (no file on disk) → inject body directly.
    for s in skills:
        if s.location is not None:
            continue
        header = f"\n\n# Skill: {s.name}"
        if s.description:
            header += f"\n{s.description}"
        parts.append(f"{header}\n\n{s.body}")

    return "\n".join(parts)
