"""Agent configuration — YAML-based entity manifest and inheritance metadata.

AgentConfig reads agent.yaml files from disk and provides a typed view
over entity manifests. Moved from core/ because from_path() does file IO
and belongs in the session engine, not the core pure-computation layer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentConfigInheritance:
    link: list[str] = field(default_factory=list)
    own: list[str] = field(default_factory=list)
    append: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentConfig:
    path: Path
    manifest: dict[str, Any]
    inheritance: AgentConfigInheritance

    @property
    def extends(self) -> str | None:
        value = self.manifest.get("extends")
        return str(value) if value else None

    @classmethod
    def from_path(cls, path: Path) -> "AgentConfig":
        try:
            import yaml
        except ImportError as exc:
            raise ImportError("Install pyyaml to use AgentConfig: pip install pyyaml") from exc

        path = Path(path)
        manifest_path = path if path.name == "agent.yaml" else path / "agent.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"agent.yaml not found: {manifest_path}")

        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        inheritance = AgentConfigInheritance(
            link=_string_list(manifest.get("link")),
            own=_string_list(manifest.get("own")),
            append=_string_list(manifest.get("append")),
        )
        return cls(path=manifest_path.parent, manifest=manifest, inheritance=inheritance)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]
