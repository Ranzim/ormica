"""Smoke test for the benchmark harness — runs it tiny, as a user would.

Uses a subprocess so the distributed benchmark's spawned worker processes can
re-import the module cleanly. Just asserts it completes without error.
"""
import subprocess
import sys
from pathlib import Path

_BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "bench.py"


def test_benchmark_suite_runs_tiny():
    proc = subprocess.run(
        [sys.executable, str(_BENCH), "--tasks", "30", "--workers", "2", "--nodes", "100"],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    for section in ("Throughput", "Caching", "Distributed", "Memory"):
        assert section in out
