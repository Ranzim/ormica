"""Composable Constitution packs — pre-built rule bundles addressable by name.

A pack is a yaml file with a list of rule specs (same format as
``constitution.rules`` in ormica.yaml). Bundled packs live in this
directory and are referenced by their stem:

    constitution:
      packs: [ftc-endorsement, credential-leak-guard]
      rules:
        - max_tokens: 30000        # inline rules still work, merged on top

A user-supplied path (contains ``/`` or ends in ``.yaml``/``.yml``) is
loaded directly from disk so teams can ship their own packs without
patching the package.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

_PACKAGE = "ormica.cortex.packs"

__all__ = ["load_pack", "available_packs"]


def load_pack(name_or_path: str) -> list[Any]:
    """Resolve ``name_or_path`` to a flat list of rule specs.

    - Bundled name (e.g. ``"ftc-endorsement"``) → looks up
      ``ormica/cortex/packs/<name>.yaml``.
    - Path (contains ``/`` or ends in ``.yaml``/``.yml``) → reads the file.

    Raises :class:`ValueError` on unknown bundled names (with the list
    of available packs) and on malformed pack files.
    """
    data = _read_pack(name_or_path)
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ValueError(
            f"pack {name_or_path!r}: 'rules' must be a list, "
            f"got {type(rules).__name__}"
        )
    return rules


def available_packs() -> list[str]:
    """Names (stems) of every yaml pack bundled with the package."""
    pack_dir = resources.files(_PACKAGE)
    return sorted(
        p.name.removesuffix(".yaml")
        for p in pack_dir.iterdir()
        if p.name.endswith(".yaml")
    )


def _read_pack(name_or_path: str) -> dict[str, Any]:
    if _looks_like_path(name_or_path):
        path = Path(name_or_path)
        if not path.exists():
            raise ValueError(f"pack file not found: {path}")
        text = path.read_text()
    else:
        try:
            text = resources.files(_PACKAGE).joinpath(
                f"{name_or_path}.yaml"
            ).read_text()
        except (FileNotFoundError, IsADirectoryError):
            available = ", ".join(available_packs()) or "(none)"
            raise ValueError(
                f"unknown pack {name_or_path!r}. "
                f"Available bundled packs: {available}. "
                f"To load a custom pack, pass a path ending in .yaml/.yml."
            ) from None

    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"pack {name_or_path!r}: top level must be a mapping, "
            f"got {type(data).__name__}"
        )
    return data


def _looks_like_path(s: str) -> bool:
    return "/" in s or "\\" in s or s.endswith((".yaml", ".yml"))
