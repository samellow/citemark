"""The component manifest (UI kit 4): `design/components.yaml` lists every component of the four
surfaces with its renderers, phase, states and strings. It's the one hand-kept part of the build
status; the gallery reads it, and Phase 2's status page will too."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

KIT = Path(__file__).resolve().parents[3]
MANIFEST = KIT / "design" / "components.yaml"


class ManifestError(Exception):
    """The manifest can't be read. The message is one plain sentence."""


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    layer: Literal["foundation", "primitive", "report", "demo", "widget", "admin"]
    renderers: list[Literal["J", "R", "P", "L", "CSS", "All"]]
    phase: Literal["1", "1-2", "2", "3"]
    states: list[str]
    strings: list[str]  # file:key, from content/en/
    spec: str
    prototype: str | None

    @field_validator("strings")
    @classmethod
    def _file_and_key(cls, keys: list[str]) -> list[str]:
        for key in keys:
            file, _, name = key.partition(":")
            if not file or not name:
                raise ValueError(f"{key} isn't file:key")
        return keys

    @property
    def slug(self) -> str:
        """The name as a path: StateMark becomes state-mark."""
        return "".join(f"-{c.lower()}" if c.isupper() and i else c.lower() for i, c in enumerate(self.name))


class _File(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: list[Component]


def load(path: Path = MANIFEST) -> dict[str, Component]:
    """The components by name, in the manifest's order."""
    try:
        data = _File.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ManifestError(f"{path} can't be read as the component manifest: {exc}") from exc
    found: dict[str, Component] = {}
    for component in data.components:
        if component.name in found:
            raise ManifestError(f"{component.name} is in {path.name} twice.")
        if len(set(component.states)) != len(component.states):
            raise ManifestError(f"{component.name} lists a state twice.")
        found[component.name] = component
    return found
