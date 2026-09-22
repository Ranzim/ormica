"""Tests for the ops CLI commands: worker / resume / plan and run --preference/--heal."""
from pathlib import Path

from ormica.cli.main import main


def _config(tmp_path: Path) -> str:
    p = tmp_path / "o.yaml"
    assert main(["init", "Demo", "--out", str(p)]) == 0
    return str(p)


def test_worker_drains_and_reports(tmp_path, capsys):
    rc = main(["worker", "--id", "w1", "--config", _config(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "w1" in out and "processed=" in out


def test_resume_with_nothing_persisted(tmp_path, capsys):
    rc = main(["resume", "--config", _config(tmp_path), "--quiet"])
    assert rc == 0
    assert "processed=" in capsys.readouterr().out


def test_run_accepts_preference_and_heal(tmp_path, capsys):
    rc = main(["run", "--config", _config(tmp_path),
               "--preference", "quality", "--heal", "--quiet"])
    assert rc == 0


def test_plan_handles_non_planner_brain_gracefully(capsys):
    # a plain mock isn't a planner → graceful error, not a crash
    rc = main(["plan", "ship a feature", "--brain", "mock"])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_worker_requires_id(tmp_path):
    import pytest

    with pytest.raises(SystemExit):        # --id is required
        main(["worker", "--config", _config(tmp_path)])
