"""Colony registry — maps colony name strings to Colony classes."""
from __future__ import annotations

from .base import Colony

_COLONIES: dict[str, type[Colony]] = {}


def register(cls: type[Colony]) -> type[Colony]:
    """Decorator: register a :class:`Colony` subclass by its ``name``."""
    if not cls.name:
        raise ValueError(
            f"Colony {cls.__name__} must set a non-empty ``name`` to be registered"
        )
    _COLONIES[cls.name] = cls
    return cls


def get_colony(name: str) -> type[Colony]:
    try:
        return _COLONIES[name]
    except KeyError as exc:
        available = ", ".join(sorted(_COLONIES)) or "(none registered)"
        raise KeyError(
            f"Unknown colony {name!r}. Available: {available}"
        ) from exc


def colonies() -> list[str]:
    return sorted(_COLONIES)
