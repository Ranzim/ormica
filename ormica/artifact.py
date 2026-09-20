"""Typed artifacts — schema-checked structured outputs.

Agents pass results as free text by default. That's fine for prose, but the
moment one agent's output is another's *input* — a DAG dependency, a delegated
subtask, a tool argument — free text is fragile: the consumer has to re-parse,
and a malformed answer only fails downstream.

An :class:`Artifact` is a structured, self-describing result: a ``kind`` label
plus a ``data`` payload validated against an :class:`ArtifactType`. Types are
declared with plain Python types (nesting allowed), so there's no dependency on
pydantic or a schema library.

    Estimate = ArtifactType("estimate", {"cost": float, "days": int, "risks": list})
    art = Estimate.parse(response.content)   # raises ArtifactError if it doesn't fit
    art.data["cost"]                          # a real float, ready to use

The payoff compounds with grounding: :func:`ormica.cortex.artifact_oracle`
turns a type into a verify-stage oracle, so an agent that emits malformed
structured output is told exactly what was wrong and retries. Artifacts also
serialize (:meth:`Artifact.to_record` / :meth:`from_record`), so they persist
and travel the same way tasks and the tree do.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Union

__all__ = ["Artifact", "ArtifactType", "ArtifactError"]


class ArtifactError(ValueError):
    """An artifact could not be parsed or failed validation.

    The message lists every problem found, so it can be fed straight back to a
    model as retry feedback.
    """


# Python type -> the word we use in problem messages / for number widening.
_TYPE_WORD = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}
_WORD_TYPE = {word: typ for typ, word in _TYPE_WORD.items()}

FieldSpec = Union[type, "ArtifactType"]


def _extract_json(text: str) -> Any:
    """Pull a JSON value out of a possibly markdown-fenced / chatty reply."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    # Fall back to the widest {...} / [...] slice in the text.
    openers = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if openers:
        start = min(openers)
        end = max(t.rfind("}"), t.rfind("]"))
        if end > start:
            try:
                return json.loads(t[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise ArtifactError("response was not valid JSON")


def _type_problems(fieldname: str, value: Any, expected: FieldSpec) -> list[str]:
    """Problems with a single field's value against its expected type."""
    if isinstance(expected, ArtifactType):
        if not isinstance(value, dict):
            return [f"field {fieldname!r} should be an object ({expected.name})"]
        return [f"{fieldname}.{p}" for p in expected.problems(value)]

    # bool is a subclass of int — keep them distinct so an int field rejects True.
    if expected is bool:
        ok = isinstance(value, bool)
    elif expected is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif expected is float:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        ok = isinstance(value, expected)

    if ok:
        return []
    want = _TYPE_WORD.get(expected, getattr(expected, "__name__", str(expected)))
    got = _TYPE_WORD.get(type(value), type(value).__name__)
    return [f"field {fieldname!r} should be {want}, got {got}"]


@dataclass
class ArtifactType:
    """A named, schema-checked shape for structured results.

    ``fields`` maps each field name to an expected Python type (``str``, ``int``,
    ``float``, ``bool``, ``list``, ``dict``) or a nested :class:`ArtifactType`.
    By default every declared field is required; pass ``required=(...)`` to make
    the rest optional. ``allow_extra=False`` rejects fields you didn't declare.
    """

    name: str
    fields: dict[str, FieldSpec]
    required: Optional[tuple[str, ...]] = None
    allow_extra: bool = True

    def problems(self, data: Any) -> list[str]:
        """Every reason ``data`` doesn't fit this type (empty list == valid)."""
        if not isinstance(data, dict):
            got = _TYPE_WORD.get(type(data), type(data).__name__)
            return [f"expected an object for {self.name!r}, got {got}"]

        req = set(self.fields) if self.required is None else set(self.required)
        probs = [f"missing required field {f!r}" for f in sorted(req) if f not in data]
        for fname, expected in self.fields.items():
            if fname in data:
                probs.extend(_type_problems(fname, data[fname], expected))
        if not self.allow_extra:
            for fname in sorted(set(data) - set(self.fields)):
                probs.append(f"unexpected field {fname!r}")
        return probs

    def validate(self, data: Any) -> None:
        """Raise :class:`ArtifactError` listing all problems, if any."""
        probs = self.problems(data)
        if probs:
            raise ArtifactError(f"invalid {self.name}: " + "; ".join(probs))

    def parse(self, source: Any) -> "Artifact":
        """Coerce ``source`` (JSON text or an already-parsed value) into a
        validated :class:`Artifact` of this kind. Raises :class:`ArtifactError`."""
        data = source if isinstance(source, (dict, list)) else _extract_json(str(source))
        self.validate(data)
        return Artifact(kind=self.name, data=data)

    def to_record(self) -> dict:
        """Serialize the type itself to a JSON-safe record.

        Lets a task's output contract survive persistence — e.g. a distributed
        worker reloads a task from the shared store and still knows to validate
        its answer. Field types become their type-word (``"integer"``, …);
        nested :class:`ArtifactType` fields recurse.
        """
        fields: dict = {}
        for name, spec in self.fields.items():
            fields[name] = spec.to_record() if isinstance(spec, ArtifactType) else _TYPE_WORD[spec]
        return {
            "name": self.name,
            "fields": fields,
            "required": list(self.required) if self.required is not None else None,
            "allow_extra": self.allow_extra,
        }

    @classmethod
    def from_record(cls, rec: dict) -> "ArtifactType":
        fields: dict = {}
        for name, spec in rec["fields"].items():
            fields[name] = cls.from_record(spec) if isinstance(spec, dict) else _WORD_TYPE[spec]
        req = rec.get("required")
        return cls(
            name=rec["name"],
            fields=fields,
            required=tuple(req) if req is not None else None,
            allow_extra=rec.get("allow_extra", True),
        )


@dataclass
class Artifact:
    """A structured, self-describing result: a ``kind`` label + a ``data`` payload.

    ``data`` is JSON-serializable (dict/list/scalar). ``meta`` carries optional
    provenance (author id, task id, tokens) that consumers may ignore.
    """

    kind: str
    data: Any
    meta: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience for object payloads: ``artifact.get("cost")``."""
        return self.data.get(key, default) if isinstance(self.data, dict) else default

    def to_record(self) -> dict:
        """Serialize to a JSON-safe record (mirrors Task / Node persistence)."""
        return {"kind": self.kind, "data": self.data, "meta": dict(self.meta)}

    @classmethod
    def from_record(cls, rec: dict) -> "Artifact":
        return cls(kind=rec["kind"], data=rec.get("data"), meta=dict(rec.get("meta", {})))
