"""Tests for the stdlib web dashboard.

Boots a real ThreadingHTTPServer on a free port, hits each route with
urllib, and asserts the HTML carries the expected markers. SSE is
tested by reading a single frame and confirming a notify() lands.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
from contextlib import closing
from typing import Optional

import pytest

from ormica import Ormica
from ormica.brain import MockBrain
from ormica.cortex import Constitution
from ormica.cortex.rules import block_role, max_depth
from ormica.dashboard import SSEObserver
from ormica.dashboard.server import DashboardHandler, _ThreadingHTTPServer
from ormica.observe import Event, TraceObserver


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def org_with_state(tmp_path):
    """An Ormica with a sample run already executed — tree, signals, rules, traces."""
    db = tmp_path / "dash.db"
    org = Ormica(
        "Dashboard Demo",
        memory_db=str(db),
        constitution=Constitution([max_depth(4), block_role("legal")]),
    )
    org.spawn("triage", role="triage")
    org.spawn("billing", role="billing")
    org.signals.emit("ticket_arrived", strength=2.0, by=org.root.id)
    org.signals.emit("escalation_needed", strength=1.0, by=org.root.id)
    org.subscribe(TraceObserver(store=org.memory))
    org.task("look at billing", dept="billing")
    org.run(brain=MockBrain(replies=["all clear"]))
    return org


@pytest.fixture
def dashboard(org_with_state):
    """Start the dashboard server in a thread and tear it down after the test."""
    port = _free_port()
    sse = SSEObserver()
    org_with_state.subscribe(sse)
    DashboardHandler.org = org_with_state
    DashboardHandler.sse = sse

    server = _ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    yield base, sse, org_with_state

    server.shutdown()
    server.server_close()


def _get(base: str, path: str, *, timeout: float = 3.0) -> tuple[int, str]:
    with urllib.request.urlopen(base + path, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def test_healthz_returns_ok(dashboard):
    base, _, _ = dashboard
    status, body = _get(base, "/healthz")
    assert status == 200
    assert body == "ok"


def test_unknown_route_404s(dashboard):
    base, _, _ = dashboard
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base, "/nope")
    assert exc.value.code == 404


def test_overview_renders_basic_counts(dashboard):
    base, _, org = dashboard
    status, body = _get(base, "/")
    assert status == 200
    assert "Dashboard Demo" in body
    assert "colony:" in body
    # nav present
    for label in ("overview", "tree", "rules", "signals", "traces"):
        assert f">{label}<" in body
    # The overview includes an EventSource bootstrap script.
    assert "EventSource" in body


def test_tree_page_lists_every_node(dashboard):
    base, _, _ = dashboard
    _, body = _get(base, "/tree")
    for name in ("triage", "billing", "Dashboard Demo"):
        assert name in body


def test_rules_page_shows_org_wide_rules(dashboard):
    base, _, _ = dashboard
    _, body = _get(base, "/rules")
    assert "max_depth_4" in body
    assert "block_role_legal" in body


def test_signals_page_lists_emitted_topics(dashboard):
    base, _, _ = dashboard
    _, body = _get(base, "/signals")
    assert "ticket_arrived" in body
    assert "escalation_needed" in body
    # Stronger trail rendered before the weaker one (sorted desc).
    assert body.index("ticket_arrived") < body.index("escalation_needed")


def test_traces_list_links_to_stored_traces(dashboard):
    base, _, org = dashboard
    _, body = _get(base, "/traces")
    # At least one persisted task → its id appears as a link.
    task_ids = [
        e.key.split("/", 1)[1]
        for e in org.memory.all()
        if e.key.startswith("traces/")
    ]
    assert task_ids, "fixture should have produced traces"
    assert task_ids[0] in body
    assert "/traces/" in body


def test_trace_detail_renders_thought_trail(dashboard):
    base, _, org = dashboard
    task_id = next(
        e.key.split("/", 1)[1]
        for e in org.memory.all()
        if e.key.startswith("traces/")
    )
    _, body = _get(base, f"/traces/{task_id}")
    assert task_id in body
    assert "think calls" in body


def test_trace_detail_missing_id_shows_empty_message(dashboard):
    base, _, _ = dashboard
    _, body = _get(base, "/traces/does-not-exist")
    assert "no trace stored" in body


def test_sse_endpoint_streams_a_notified_event(dashboard):
    """End-to-end: hit /events, notify() into the SSE observer, read one frame."""
    base, sse, _ = dashboard

    captured: list[bytes] = []

    def reader():
        try:
            with urllib.request.urlopen(base + "/events", timeout=5.0) as resp:
                # Drain the priming "connected" comment, then up to one data frame.
                start = time.time()
                while time.time() - start < 4.0:
                    line: Optional[bytes] = resp.readline()
                    if not line:
                        break
                    captured.append(line)
                    if line.startswith(b"data:"):
                        return
        except Exception:
            return

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    # Wait briefly for the connection to register, then notify.
    time.sleep(0.2)
    sse.notify(
        Event(
            type="task.done",
            source="test",
            payload={"task_id": "abc123", "tokens_used": 7},
        )
    )

    t.join(timeout=4.5)

    data_lines = [line for line in captured if line.startswith(b"data:")]
    assert data_lines, f"no SSE data frame received; captured={captured!r}"
    decoded = json.loads(data_lines[0][len(b"data: ") :].decode("utf-8"))
    assert decoded["type"] == "task.done"
    assert decoded["payload"]["task_id"] == "abc123"
