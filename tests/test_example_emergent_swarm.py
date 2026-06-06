"""Smoke test — the bundled `emergent_swarm` demo must keep running end-to-end.

CI runs this on every push. If any public API used in the demo drifts —
`org.spawn`, `org.write`, `org.emit`, `org.top_signals`, `Constitution`,
`@tool`, `Agent.act_with_tools`, MockBrain reply types — the test fails
loudly. That way new contributors can trust the example as a working
reference, not stale documentation.
"""
from __future__ import annotations

import runpy
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "emergent_swarm.py"


def test_emergent_swarm_example_runs_end_to_end(capsys):
    runpy.run_path(str(EXAMPLE), run_name="__main__")
    out = capsys.readouterr().out

    # arbor: tree grew from 1 root to 4 nodes
    for zone in ("north", "east", "south"):
        assert zone in out, f"expected zone {zone!r} in output, got:\n{out}"

    # stigma: pheromone trails ranked, east strongest at 3.00
    assert "trail/east" in out
    assert "strength=3.00" in out

    # mycelium: persistent author-tagged notes
    assert "zones/east/scouted" in out

    # canopy / cortex: Constitution denied the escalate() attempt;
    # the scout's final sentence mentions the denial.
    assert "denied" in out.lower()

    # brain + tools: 5 turns (3 delegations + 1 denied escalate + 1 final text)
    assert "brain.calls = 5" in out
