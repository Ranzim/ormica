"""Tool, ToolCall, and the @tool decorator — the function-calling layer."""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, get_type_hints


@dataclass
class Tool:
    """A callable an agent can invoke during ``act_with_tools``.

    ``fn`` is the Python function that actually runs. ``schema`` is the
    JSON-Schema object the LLM sees describing the inputs; the default
    is derived from ``fn``'s signature and docstring via :func:`tool`.
    """

    name: str
    description: str
    fn: Callable[..., Any]
    schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})

    def __call__(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)


@dataclass
class ToolCall:
    """A model's request to invoke a tool."""

    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """The outcome of a tool call. ``is_error`` lets the model adjust."""

    call_id: str
    content: str
    is_error: bool = False


# Type → JSON-Schema primitive mapping
_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def tool(
    fn: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Any:
    """Decorator: turn a typed Python function into a :class:`Tool`.

    Usage::

        @tool
        def get_weather(city: str, unit: str = "celsius") -> str:
            \"\"\"Look up the current weather in a city.\"\"\"
            ...

    The JSON-Schema for arguments is derived from the function's type
    hints and signature. Parameters without defaults become required.
    The first line of the docstring becomes the tool description.
    """

    def wrap(f: Callable[..., Any]) -> Tool:
        return Tool(
            name=name or f.__name__,
            description=description or _first_doc_line(f),
            fn=f,
            schema=_schema_from_signature(f),
        )

    return wrap if fn is None else wrap(fn)


def _first_doc_line(fn: Callable[..., Any]) -> str:
    doc = inspect.getdoc(fn) or ""
    return doc.split("\n", 1)[0].strip()


def _schema_from_signature(fn: Callable[..., Any]) -> dict:
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    properties: dict[str, dict] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        hint = hints.get(name, str)
        properties[name] = {"type": _JSON_TYPES.get(hint, "string")}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema
