"""Unit tests for ormica.observe.export — trace_to_json, traces_to_jsonl, CSV variants."""
from __future__ import annotations

import csv
import io
import json

from ormica.observe import (
    Trace,
    TraceEntry,
    trace_to_dict,
    trace_to_json,
    traces_to_csv_detail,
    traces_to_csv_summary,
    traces_to_jsonl,
)


def _trace(task_id="t1", *, target="sales", description="say hi",
           status="done", entries=None, error=None) -> Trace:
    return Trace(
        task_id=task_id,
        node_id="n1",
        target=target,
        description=description,
        started_at=1_000_000.0,
        ended_at=1_000_001.5,
        status=status,
        result=None,
        error=error,
        entries=entries or [
            TraceEntry(
                timestamp=1_000_000.5,
                messages=[{"role": "user", "content": "hello"}],
                system="be friendly",
                tool_names=["greet"],
                response_content="hi there",
                response_tool_calls=[],
                tokens_used=12,
            ),
        ],
    )


# --- single-trace JSON --------------------------------------------------------


def test_trace_to_dict_preserves_every_field():
    t = _trace()
    d = trace_to_dict(t)
    assert d["task_id"] == "t1"
    assert d["target"] == "sales"
    assert d["status"] == "done"
    assert len(d["entries"]) == 1
    assert d["entries"][0]["tokens_used"] == 12
    assert d["entries"][0]["response_content"] == "hi there"


def test_trace_to_json_round_trips_through_json_loads():
    t = _trace()
    text = trace_to_json(t)
    back = json.loads(text)
    assert back["task_id"] == "t1"
    assert back["entries"][0]["messages"][0]["content"] == "hello"


# --- bulk JSONL ---------------------------------------------------------------


def test_traces_to_jsonl_one_line_per_trace():
    a, b = _trace("a"), _trace("b")
    text = traces_to_jsonl([a, b])
    lines = text.splitlines()
    assert len(lines) == 2
    ids = [json.loads(line)["task_id"] for line in lines]
    assert ids == ["a", "b"]


def test_traces_to_jsonl_lines_each_stand_alone():
    """Each line must be valid JSON on its own — streaming-friendly."""
    text = traces_to_jsonl(_trace(f"t{i}") for i in range(3))
    for line in text.splitlines():
        # If any line was concatenated or missing a separator, json.loads would
        # raise; just succeeding here is the assertion.
        json.loads(line)


# --- CSV summary --------------------------------------------------------------


def test_csv_summary_has_one_row_per_task_plus_header():
    rows = list(csv.reader(io.StringIO(
        traces_to_csv_summary([_trace("a"), _trace("b")])
    )))
    assert rows[0] == [
        "task_id", "target", "description", "status",
        "n_think_calls", "total_tokens", "started_at", "ended_at", "error",
    ]
    assert len(rows) == 3
    assert rows[1][0] == "a"
    assert rows[1][4] == "1"      # n_think_calls
    assert rows[1][5] == "12"     # total_tokens (one entry, 12 tokens)


def test_csv_summary_collapses_newlines_in_description():
    """A multi-line description must not split the CSV row."""
    t = _trace(description="line1\nline2\rline3")
    rows = list(csv.reader(io.StringIO(traces_to_csv_summary([t]))))
    assert len(rows) == 2
    assert "\n" not in rows[1][2]
    assert "line1 line2 line3" in rows[1][2]


# --- CSV detail --------------------------------------------------------------


def test_csv_detail_has_one_row_per_think_call():
    multi = _trace(entries=[
        TraceEntry(timestamp=0.0, messages=[], system="", tool_names=[],
                   response_content="a", response_tool_calls=[], tokens_used=3),
        TraceEntry(timestamp=1.0, messages=[], system="", tool_names=["t"],
                   response_content="b", response_tool_calls=[], tokens_used=5),
    ])
    rows = list(csv.reader(io.StringIO(traces_to_csv_detail([multi]))))
    assert rows[0] == [
        "task_id", "target", "task_status", "call_index", "timestamp",
        "tokens_used", "tool_names", "response_preview", "n_messages",
    ]
    assert len(rows) == 3
    assert rows[1][3] == "1"  # call_index
    assert rows[2][3] == "2"
    assert rows[2][5] == "5"  # tokens_used
    assert rows[2][6] == "t"  # tool_names joined


def test_csv_detail_truncates_long_responses():
    t = _trace(entries=[TraceEntry(
        timestamp=0.0, messages=[], system="", tool_names=[],
        response_content="x" * 1000, response_tool_calls=[], tokens_used=1,
    )])
    rows = list(csv.reader(io.StringIO(traces_to_csv_detail([t]))))
    preview = rows[1][7]
    assert len(preview) <= 200
    assert preview.endswith("…")


def test_export_handles_empty_iterable_cleanly():
    """JSONL/CSV exports of zero traces still produce a valid header / empty body."""
    assert traces_to_jsonl([]) == ""
    summary = traces_to_csv_summary([])
    assert summary.splitlines()[0].startswith("task_id,")
    detail = traces_to_csv_detail([])
    assert detail.splitlines()[0].startswith("task_id,")
