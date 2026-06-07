"""Load a Colony from a YAML file — declarative industries without writing Python."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml

from .base import AgentTemplate, Colony
from .registry import register as register_fn


def load_colony(
    path: Union[str, Path],
    *,
    register: bool = False,
) -> type[Colony]:
    """Build a :class:`Colony` subclass from a YAML spec.

    YAML shape::

        name: saas
        description: B2B SaaS organization
        templates:
          - name: product
            role: product
            task: Define and ship features
            system_prompt: |
              You lead product. Prioritize, scope, and ship.
          - name: engineering
            role: engineering
            ...

    If ``register=True``, the colony is added to the global registry
    and can be planted via ``org.plant(name)``.
    """
    path = Path(path)
    data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}

    name = data.get("name")
    if not name:
        raise ValueError(f"colony YAML at {path} is missing required 'name' field")

    raw_templates = data.get("templates") or []
    if not isinstance(raw_templates, list):
        raise ValueError(
            f"colony YAML at {path}: 'templates' must be a list, got {type(raw_templates).__name__}"
        )

    templates: list[type[AgentTemplate]] = [
        _make_template(spec, path=path) for spec in raw_templates
    ]

    description = data.get("description", "")
    colony_cls = type(
        _classname_for(name) + "Colony",
        (Colony,),
        {
            "name": name,
            "description": description,
            "templates": (lambda _ts=tuple(templates): lambda self: list(_ts))(),
        },
    )

    if register:
        register_fn(colony_cls)

    return colony_cls


def _make_template(spec: Any, *, path: Path) -> type[AgentTemplate]:
    if not isinstance(spec, dict):
        raise ValueError(
            f"colony YAML at {path}: each template entry must be a mapping, got {type(spec).__name__}"
        )
    if not spec.get("name") and not spec.get("role"):
        raise ValueError(
            f"colony YAML at {path}: each template needs at least 'name' or 'role': {spec!r}"
        )

    base_name = spec.get("name") or spec.get("role")
    rule_specs = spec.get("rules") or []
    if rule_specs:
        from ormica.cortex.loader import build_rule

        rules = tuple(build_rule(r) for r in rule_specs)
    else:
        rules = ()

    return type(
        _classname_for(base_name) + "Agent",
        (AgentTemplate,),
        {
            "name": spec.get("name", ""),
            "role": spec.get("role", ""),
            "task": spec.get("task", ""),
            "system_prompt": spec.get("system_prompt", ""),
            "rules": rules,
        },
    )


def _classname_for(name: str) -> str:
    # "supply_chain" → "SupplyChain"; "saas" → "Saas"
    return "".join(part.capitalize() for part in name.replace("-", "_").split("_"))
