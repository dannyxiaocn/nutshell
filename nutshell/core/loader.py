from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class BaseLoader(ABC, Generic[T]):
    """Abstract base for loaders that read external files into nutshell objects."""

    @abstractmethod
    def load(self, path: Path) -> T: ...

    @abstractmethod
    def load_dir(self, directory: Path) -> list[T]: ...


@dataclass(frozen=True)
class AgentConfigInheritance:
    link: list[str] = field(default_factory=list)
    own: list[str] = field(default_factory=list)
    append: list[str] = field(default_factory=list)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


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


__all__ = ["BaseLoader", "AgentConfig", "AgentConfigInheritance"]
