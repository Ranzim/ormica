"""ormica.yaml — config dataclasses and YAML load/save."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class BrainConfig:
    type: str = "mock"
    model: str = "claude-opus-4-7"
    replies: list[str] = field(default_factory=lambda: ["ok"])


@dataclass
class TaskConfig:
    """One task line in ``ormica.yaml``.

    ``dept`` and ``target`` are **aliases** — both route the task to a node
    by name (see :func:`ormica.cli.main.cmd_run` and ``runtime.Task.target``).
    If both are set, ``dept`` wins (see ``cli/main.py``: ``dept=t.dept or t.target``).
    When both are empty, the task lands at the org root.

    Pick whichever name reads better for you:

    - ``dept: sales`` reads naturally for org-chart-style colonies
      (the two built-in colonies — ``business``, ``supply_chain`` — both expose
      department-named nodes).
    - ``target: sales`` reads more generically for "any named node in the tree."
    """

    description: str
    dept: str = ""
    target: str = ""
    priority: str = "normal"


@dataclass
class ConstitutionConfig:
    """Org-wide rules declared in ``ormica.yaml``.

    Each entry in ``rules`` is a declarative spec consumed by
    :func:`ormica.cortex.loader.build_rule` — either a bare factory name
    (string) or a single-key mapping with the factory's positional arg.
    """

    rules: list = field(default_factory=list)


@dataclass
class OrmicaConfig:
    name: str = "My Company"
    owner: str = ""
    industry: str = ""
    max_depth: int = 8
    memory_file: str = ""
    memory_db: str = ""
    brain: BrainConfig = field(default_factory=BrainConfig)
    tasks: list[TaskConfig] = field(default_factory=list)
    constitution: Optional[ConstitutionConfig] = None


def load_config(path: Path) -> OrmicaConfig:
    data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    brain = BrainConfig(**(data.pop("brain", None) or {}))
    tasks = [TaskConfig(**t) for t in (data.pop("tasks", None) or [])]
    constitution_raw = data.pop("constitution", None)
    constitution = (
        ConstitutionConfig(**constitution_raw) if constitution_raw else None
    )
    return OrmicaConfig(
        brain=brain, tasks=tasks, constitution=constitution, **data
    )


def save_config(config: OrmicaConfig, path: Path) -> None:
    payload = asdict(config)
    # Drop ``constitution: null`` from the output — keeps init'd configs clean.
    if payload.get("constitution") is None:
        payload.pop("constitution", None)
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
