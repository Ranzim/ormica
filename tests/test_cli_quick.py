"""Tests for the quick, config-free CLI commands: ask / solve / doctor / version / health."""
from ormica.cli.main import main


def test_version_prints_semver(capsys):
    assert main(["version"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.count(".") >= 2   # e.g. 0.9.0


def test_ask_runs_with_mock_brain(capsys):
    rc = main(["ask", "hello?", "--brain", "mock"])
    assert rc == 0
    assert "ok" in capsys.readouterr().out   # MockBrain default reply


def test_ask_routes_to_a_named_target(capsys):
    rc = main(["ask", "analyse", "--brain", "mock", "--target", "analyst"])
    assert rc == 0
    assert "ok" in capsys.readouterr().out


def test_ask_accepts_preference(capsys):
    assert main(["ask", "hi", "--brain", "mock", "--preference", "quality"]) == 0


def test_solve_runs_with_mock_brain(capsys):
    rc = main(["solve", "plan a launch", "--brain", "mock", "--preference", "speed"])
    assert rc == 0
    assert capsys.readouterr().out.strip()   # some answer printed


def test_doctor_reports_without_leaking_keys(capsys, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value-xyz")
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "ormica doctor" in out
    assert "GEMINI_API_KEY" in out
    assert "set" in out
    assert "super-secret-value-xyz" not in out   # value must never be printed


def test_health_requires_config(capsys, tmp_path):
    rc = main(["health", "--config", str(tmp_path / "nope.yaml")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err
