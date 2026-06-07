"""Trace export — turn stored Thought Trails into portable JSON and CSV.

JSON preserves the full structure (one task = one JSON object). For bulk
output use JSON Lines (one trace per line) so an exported file stays
streamable even when the colony has thousands of traces.

CSV ships in two shapes:

- ``summary`` — one row per task, with totals (think calls, tokens).
- ``detail``  — one row per think call within a task, with the call's
  token cost and a truncated response preview.

The functions here are pure — they take a :class:`Trace` or an iterable
of them and return strings or dicts. No file I/O, no CLI assumptions.
The CLI's ``ormica export`` subcommand and ``ormica trace --format json``
are thin wrappers on top.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from typing import Any, Iterable

from .trace import Trace


def trace_to_dict(trace: Trace) -> dict:
    """Serialize a :class:`Trace` (and its nested :class:`TraceEntry` list) to a plain dict."""
    return asdict(trace)


def trace_to_json(trace: Trace, *, indent: int | None = 2) -> str:
    """Render a single trace as a JSON document."""
    return json.dumps(trace_to_dict(trace), indent=indent, default=str)


def traces_to_jsonl(traces: Iterable[Trace]) -> str:
    """Render many traces as JSON Lines (one compact object per line).

    Streamable: each line stands alone, so the output file can be fed to
    ``jq``/Spark/BigQuery without first loading the whole thing.
    """
    return "\n".join(
        json.dumps(trace_to_dict(t), default=str, separators=(",", ":"))
        for t in traces
    )


def traces_to_csv_summary(traces: Iterable[Trace]) -> str:
    """One row per task: high-level audit view."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "task_id",
            "target",
            "description",
            "status",
            "n_think_calls",
            "total_tokens",
            "started_at",
            "ended_at",
            "error",
        ]
    )
    for t in traces:
        total_tokens = sum(e.tokens_used for e in t.entries)
        writer.writerow(
            [
                t.task_id,
                t.target,
                _safe(t.description),
                t.status,
                len(t.entries),
                total_tokens,
                t.started_at,
                t.ended_at,
                _safe(t.error or ""),
            ]
        )
    return buf.getvalue()


def traces_to_csv_detail(traces: Iterable[Trace]) -> str:
    """One row per think call: per-decision audit view."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "task_id",
            "target",
            "task_status",
            "call_index",
            "timestamp",
            "tokens_used",
            "tool_names",
            "response_preview",
            "n_messages",
        ]
    )
    for t in traces:
        for i, entry in enumerate(t.entries, start=1):
            writer.writerow(
                [
                    t.task_id,
                    t.target,
                    t.status,
                    i,
                    entry.timestamp,
                    entry.tokens_used,
                    "|".join(entry.tool_names),
                    _safe(_truncate(entry.response_content, 200)),
                    len(entry.messages),
                ]
            )
    return buf.getvalue()


# --- helpers ------------------------------------------------------------------


def _safe(s: Any) -> str:
    """CSV-safe: collapse newlines so a multi-line description stays one cell."""
    return str(s).replace("\n", " ").replace("\r", " ")


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"
