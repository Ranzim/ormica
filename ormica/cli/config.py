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

    ``rules`` — declarative specs consumed by
    :func:`ormica.cortex.loader.build_rule` (bare factory name or
    single-key mapping with the factory's positional arg).

    ``packs`` — names or paths of pre-built rule bundles
    (see :mod:`ormica.cortex.packs`). Pack rules are expanded first,
    then inline ``rules`` are appended — so a later inline rule can
    augment a pack but cannot remove rules from one.
    """

    rules: list = field(default_factory=list)
    packs: list = field(default_factory=list)


@dataclass
class StigmaConfig:
    """Pheromone-trail behavior declared in ``ormica.yaml``.

    ``half_life`` and ``floor`` mirror :class:`ormica.stigma.Stigma`'s
    constructor args. ``auto_emit`` controls whether the runtime
    reinforces an ``activity:<node>`` and ``topic:<target>`` trail on every
    task finalize — off in the bare :class:`Ormica` API for back-compat,
    on by default when launched via the CLI so ``ormica signals`` shows
    something useful out of the box.
    """

    half_life: float = 60.0
    floor: float = 0.01
    auto_emit: bool = True


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
    # Per-node rule overrides, keyed by node name. Each value is a list of
    # declarative rule specs (same shape as ``constitution.rules``). Attached
    # at org build time and surfaced via ``ormica rules`` / the dashboard.
    node_rules: dict[str, list] = field(default_factory=dict)
    stigma: Optional[StigmaConfig] = None


def load_config(path: Path) -> OrmicaConfig:
    data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    brain = BrainConfig(**(data.pop("brain", None) or {}))
    tasks = [TaskConfig(**t) for t in (data.pop("tasks", None) or [])]
    constitution_raw = data.pop("constitution", None)
    constitution = (
        ConstitutionConfig(**constitution_raw) if constitution_raw else None
    )
    node_rules = data.pop("node_rules", None) or {}
    if not isinstance(node_rules, dict):
        raise ValueError(
            f"node_rules must be a mapping of node-name → [rule, ...], "
            f"got {type(node_rules).__name__}"
        )
    stigma_raw = data.pop("stigma", None)
    stigma = StigmaConfig(**stigma_raw) if stigma_raw else None
    return OrmicaConfig(
        brain=brain,
        tasks=tasks,
        constitution=constitution,
        node_rules=node_rules,
        stigma=stigma,
        **data,
    )


def save_config(config: OrmicaConfig, path: Path) -> None:
    payload = asdict(config)
    # Drop empty / null fields from the output — keeps init'd configs clean.
    for key in ("constitution", "stigma"):
        if payload.get(key) is None:
            payload.pop(key, None)
    if not payload.get("node_rules"):
        payload.pop("node_rules", None)
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
