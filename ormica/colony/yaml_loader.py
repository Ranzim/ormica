"""Load a Colony from a YAML file — declarative industries without writing Python."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from ormica.arbor import Node

import yaml

from .base import AgentTemplate, Colony
from .registry import register as register_fn

# Blueprint = list of (template_cls, [child_blueprint, ...]) tuples.
# Built once at load_colony() time; walked at plant() time to spawn
# nodes in pre-order under the chosen parent.
_Blueprint = list[tuple[type[AgentTemplate], "list"]]


def load_colony(
    path: Union[str, Path],
    *,
    register: bool = False,
) -> type[Colony]:
    """Build a :class:`Colony` subclass from a YAML spec.

    YAML shape — flat (existing) or nested via ``children:``::

        name: creator-studio
        description: Solo creator running content + partnerships + finance
        templates:
          - name: creator-office
            role: chief-of-staff
            children:
              - name: content
                role: content-head
                children:
                  - name: short-form
                    role: shorts-prod
              - name: finance
                role: finance-lead

    Each ``children:`` entry has the same shape as a top-level template
    and is planted under its parent. ``children:`` is optional — colonies
    without it behave exactly like before.

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

    blueprint: _Blueprint = [_make_blueprint(spec, path=path) for spec in raw_templates]
    # Flat list of top-level template classes — preserved so existing
    # ``colony.templates()`` callers (and any external code that walked
    # them) keep working unchanged.
    top_templates: list[type[AgentTemplate]] = [b[0] for b in blueprint]

    def _plant(self, org, *, under: Optional[Node] = None) -> list[Node]:
        parent = under if under is not None else org.root
        return _plant_blueprint(blueprint, org, parent)

    description = data.get("description", "")
    colony_cls = type(
        _classname_for(name) + "Colony",
        (Colony,),
        {
            "name": name,
            "description": description,
            "plant": _plant,
            "templates": (lambda _ts=tuple(top_templates): lambda self: list(_ts))(),
        },
    )

    if register:
        register_fn(colony_cls)

    return colony_cls


def _make_blueprint(spec: Any, *, path: Path) -> tuple[type[AgentTemplate], _Blueprint]:
    """Build one ``(template_cls, [child_blueprint, ...])`` tuple from a spec.

    Recurses into ``spec["children"]``. Validation of the spec itself
    (must be a mapping, must have name or role) is delegated to
    :func:`_make_template`.
    """
    template_cls = _make_template(spec, path=path)
    children_specs = spec.get("children") if isinstance(spec, dict) else None
    if children_specs is None:
        return (template_cls, [])
    if not isinstance(children_specs, list):
        raise ValueError(
            f"colony YAML at {path}: 'children' must be a list, "
            f"got {type(children_specs).__name__}"
        )
    return (template_cls, [_make_blueprint(c, path=path) for c in children_specs])


def _plant_blueprint(
    blueprint: _Blueprint, org, parent: Node
) -> list[Node]:
    """Pre-order walk of a blueprint, returning every spawned node.

    Returns parents *and* descendants — the most useful contract for a
    deep colony (lets the caller inspect total node count, depth, etc.).
    Flat colonies (no ``children:``) return the same shape as before.
    """
    planted: list[Node] = []
    for template_cls, children in blueprint:
        node = template_cls.plant(org, under=parent)
        planted.append(node)
        if children:
            planted.extend(_plant_blueprint(children, org, node))
    return planted


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

    sense_prefixes = _parse_sense_prefixes(
        spec.get("sense_prefixes"), path=path
    )

    return type(
        _classname_for(base_name) + "Agent",
        (AgentTemplate,),
        {
            "name": spec.get("name", ""),
            "role": spec.get("role", ""),
            "task": spec.get("task", ""),
            "system_prompt": spec.get("system_prompt", ""),
            "rules": rules,
            "sense_prefixes": sense_prefixes,
        },
    )


def _parse_sense_prefixes(raw: Any, *, path: Path) -> tuple[str, ...]:
    """Normalize a sense_prefixes spec to a tuple of strings.

    YAML quirk worth absorbing here: a bare trailing-colon scalar like
    ``topic:`` parses as ``{topic: None}`` (an empty mapping value),
    and ``[topic:, activity:]`` becomes a list of such mappings. Users
    will write the obvious thing; the loader handles both forms instead
    of forcing everyone to quote ("topic:").
    """
    if raw is None or raw == "":
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, dict):
        # Single trailing-colon scalar parsed as a one-key mapping.
        return tuple(_normalize_one(item, path=path) for item in [raw])
    if isinstance(raw, (list, tuple)):
        return tuple(_normalize_one(item, path=path) for item in raw)
    raise ValueError(
        f"colony YAML at {path}: 'sense_prefixes' must be a string or list, "
        f"got {type(raw).__name__}"
    )


def _normalize_one(item: Any, *, path: Path) -> str:
    if isinstance(item, str):
        return item
    # YAML form: `topic:` (no value) parses to {"topic": None}. Treat the
    # single key as the prefix, re-appending the colon.
    if isinstance(item, dict) and len(item) == 1:
        key, value = next(iter(item.items()))
        if value is None:
            return f"{key}:"
    raise ValueError(
        f"colony YAML at {path}: each sense_prefixes entry must be a "
        f"string, got {item!r}"
    )


def _classname_for(name: str) -> str:
    # "supply_chain" → "SupplyChain"; "saas" → "Saas"
    return "".join(part.capitalize() for part in name.replace("-", "_").split("_"))
