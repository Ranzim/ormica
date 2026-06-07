"""Tests for the ormica CLI."""
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from ormica.cli.config import (
    BrainConfig,
    ConstitutionConfig,
    OrmicaConfig,
    TaskConfig,
    load_config,
    save_config,
)
from ormica.cli.main import build_parser, main


# --- config roundtrip ---------------------------------------------------------


def test_save_then_load_roundtrip(tmp_path: Path):
    cfg = OrmicaConfig(
        name="Acme",
        owner="Ranzim",
        industry="business",
        brain=BrainConfig(type="claude", model="claude-haiku-4-5"),
        tasks=[TaskConfig(description="ship it", dept="ops", priority="high")],
    )
    path = tmp_path / "ormica.yaml"
    save_config(cfg, path)
    loaded = load_config(path)
    assert asdict(loaded) == asdict(cfg)


def test_load_handles_missing_optional_sections(tmp_path: Path):
    path = tmp_path / "ormica.yaml"
    path.write_text("name: Bare\n")
    cfg = load_config(path)
    assert cfg.name == "Bare"
    assert cfg.brain.type == "mock"
    assert cfg.tasks == []


def test_load_empty_file_uses_defaults(tmp_path: Path):
    path = tmp_path / "ormica.yaml"
    path.write_text("")
    cfg = load_config(path)
    assert cfg.name == "My Company"


# --- init ---------------------------------------------------------------------


def test_init_writes_starter_config(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    rc = main(["init", "Acme", "--owner", "Ranzim", "--out", str(out)])
    assert rc == 0
    assert out.exists()

    data = yaml.safe_load(out.read_text())
    assert data["name"] == "Acme"
    assert data["owner"] == "Ranzim"
    assert data["industry"] == "business"
    assert data["brain"]["type"] == "mock"


def test_init_refuses_to_overwrite_without_force(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    out.write_text("name: existing\n")
    rc = main(["init", "Acme", "--out", str(out)])
    assert rc == 1
    assert "already exists" in capsys.readouterr().err
    # File untouched.
    assert "existing" in out.read_text()


def test_init_with_force_overwrites(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    out.write_text("name: existing\n")
    rc = main(["init", "Acme", "--out", str(out), "--force"])
    assert rc == 0
    assert yaml.safe_load(out.read_text())["name"] == "Acme"


def test_init_custom_industry(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    main(["init", "Globex", "--industry", "supply_chain", "--out", str(out)])
    assert yaml.safe_load(out.read_text())["industry"] == "supply_chain"


# --- status -------------------------------------------------------------------


def test_status_missing_config_errors(tmp_path: Path, capsys):
    rc = main(["status", "--config", str(tmp_path / "nope.yaml")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_status_prints_tree_and_tasks(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        owner="Ranzim",
        industry="business",
        tasks=[
            TaskConfig(description="follow up", dept="sales", priority="high"),
            TaskConfig(description="forecast", dept="finance"),
        ],
    )
    save_config(cfg, out)

    rc = main(["status", "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "Acme" in text
    assert "Ranzim" in text
    assert "business" in text
    assert "sales" in text
    assert "finance" in text
    assert "follow up" in text
    # business colony planted, so all 4 depts appear
    for dept in ("operations", "sales", "marketing", "finance"):
        assert dept in text


def test_status_labels_tasks_as_defined_not_queued(tmp_path: Path, capsys):
    """Issue #10: yaml-declared tasks aren't a runtime queue — don't call them 'queued'."""
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        tasks=[TaskConfig(description="t1", dept="sales")],
    )
    save_config(cfg, out)

    rc = main(["status", "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "tasks defined: 1" in text
    assert "queued" not in text


def test_status_with_unknown_industry_errors(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    save_config(OrmicaConfig(name="X", industry="does_not_exist"), out)
    rc = main(["status", "--config", str(out)])
    assert rc == 1
    assert "Unknown colony" in capsys.readouterr().err


# --- rules / signals / trace (v0.2 step 5) ----------------------------------


def test_rules_lists_org_wide_constitution(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        constitution=ConstitutionConfig(
            rules=[{"max_depth": 4}, "require_json"],
        ),
    )
    save_config(cfg, out)

    rc = main(["rules", "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "org-wide rules (2)" in text
    assert "max_depth_4" in text
    assert "require_json" in text


def test_rules_lists_per_node_rules_from_colony_yaml(tmp_path: Path, capsys):
    """Per-template rules attached via colony YAML show up under per-node rules."""
    industry_yaml = tmp_path / "ind.yaml"
    industry_yaml.write_text(yaml.safe_dump({
        "name": "rules_demo",
        "templates": [
            {"name": "finance", "role": "finance",
             "rules": [{"max_tokens": 10000}]},
        ],
    }))
    cfg_path = tmp_path / "ormica.yaml"
    save_config(OrmicaConfig(name="Acme", industry=str(industry_yaml)), cfg_path)

    try:
        rc = main(["rules", "--config", str(cfg_path)])
        assert rc == 0
        text = capsys.readouterr().out
        assert "per-node rules" in text
        assert "finance" in text
        assert "max_tokens_10000" in text
    finally:
        from ormica.colony.registry import _COLONIES
        _COLONIES.pop("rules_demo", None)


def test_rules_when_no_rules_exist(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    save_config(OrmicaConfig(name="Acme"), out)
    rc = main(["rules", "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "org-wide rules: (none)" in text
    assert "per-node rules: (none)" in text


def test_signals_reports_no_trails_on_fresh_config(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    save_config(OrmicaConfig(name="Acme"), out)
    rc = main(["signals", "--config", str(out)])
    assert rc == 0
    assert "no signals found" in capsys.readouterr().out


def test_signals_lists_emitted_trails(tmp_path: Path, capsys):
    """After a run that emits signals, `ormica signals` lists them sorted by strength."""
    out = tmp_path / "ormica.yaml"
    db = tmp_path / "memory.db"
    cfg = OrmicaConfig(
        name="Acme",
        memory_db=str(db),
    )
    save_config(cfg, out)

    # Bootstrap some signals by direct emit, then re-load via CLI.
    from ormica import Ormica
    bootstrap = Ormica("Acme", memory_db=str(db))
    bootstrap.emit("hot_lead", strength=3.0)
    bootstrap.emit("cold_call", strength=0.5)

    rc = main(["signals", "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "hot_lead" in text
    assert "cold_call" in text
    # hot_lead has the higher strength; it should appear first.
    assert text.index("hot_lead") < text.index("cold_call")


def test_trace_reports_missing_trace(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    save_config(OrmicaConfig(name="Acme"), out)
    rc = main(["trace", "ghost-task-id", "--config", str(out)])
    assert rc == 1
    assert "no trace found" in capsys.readouterr().err


def test_run_then_trace_returns_thought_trail(tmp_path: Path, capsys):
    """End-to-end: ormica run persists traces to mycelium; ormica trace reads them."""
    out = tmp_path / "ormica.yaml"
    db = tmp_path / "memory.db"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        memory_db=str(db),
        brain=BrainConfig(type="mock", replies=["scouted"]),
        tasks=[TaskConfig(description="scout", dept="sales")],
    )
    save_config(cfg, out)

    rc = main(["run", "--config", str(out)])
    assert rc == 0
    # Grab the task id from the persisted state (the runner saved it to memory).
    from ormica.mycelium import Mycelium, SqliteBackend
    mem = Mycelium(backend=SqliteBackend(str(db)))
    task_entries = [e for e in mem.all() if e.key.startswith("tasks/")]
    assert task_entries, "expected at least one persisted task"
    task_id = task_entries[0].key.split("/", 1)[1]

    # Now `ormica trace <id>` should print something.
    capsys.readouterr()  # drain
    rc = main(["trace", task_id, "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert task_id in text
    assert "scout" in text  # task description


# --- trace --format json / export (v0.2 step 2 of Phase 2) ------------------


def _run_and_get_task_id(tmp_path, capsys):
    """Helper: spin up a run that persists at least one trace, return its config and id."""
    import json as _json
    out = tmp_path / "ormica.yaml"
    db = tmp_path / "memory.db"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        memory_db=str(db),
        brain=BrainConfig(type="mock", replies=["scouted"]),
        tasks=[TaskConfig(description="scout", dept="sales")],
    )
    save_config(cfg, out)
    rc = main(["run", "--config", str(out)])
    assert rc == 0
    capsys.readouterr()  # drain
    from ormica.mycelium import Mycelium, SqliteBackend
    mem = Mycelium(backend=SqliteBackend(str(db)))
    task_id = next(
        e.key.split("/", 1)[1]
        for e in mem.all()
        if e.key.startswith("traces/")
    )
    return out, task_id, _json


def test_trace_format_json_emits_valid_json(tmp_path: Path, capsys):
    out, task_id, _json = _run_and_get_task_id(tmp_path, capsys)
    rc = main(["trace", task_id, "--config", str(out), "--format", "json"])
    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["task_id"] == task_id
    assert isinstance(payload["entries"], list)
    assert payload["entries"][0]["response_content"] == "scouted"


def test_export_json_writes_jsonl_to_stdout(tmp_path: Path, capsys):
    out, task_id, _json = _run_and_get_task_id(tmp_path, capsys)
    rc = main(["export", "--config", str(out), "--format", "json"])
    assert rc == 0
    text = capsys.readouterr().out.strip()
    # Each line is a complete JSON object — JSON Lines.
    for line in text.splitlines():
        payload = _json.loads(line)
        assert "task_id" in payload
    # And our task is represented.
    assert task_id in text


def test_export_csv_summary_is_default_csv_shape(tmp_path: Path, capsys):
    out, task_id, _ = _run_and_get_task_id(tmp_path, capsys)
    rc = main(["export", "--config", str(out), "--format", "csv"])
    assert rc == 0
    text = capsys.readouterr().out
    header, *rows = text.strip().splitlines()
    assert header.startswith("task_id,target,description,status,n_think_calls")
    assert any(task_id in row for row in rows)


def test_export_csv_detail_one_row_per_call(tmp_path: Path, capsys):
    out, task_id, _ = _run_and_get_task_id(tmp_path, capsys)
    rc = main(["export", "--config", str(out), "--format", "csv", "--mode", "detail"])
    assert rc == 0
    text = capsys.readouterr().out
    header, *rows = text.strip().splitlines()
    assert header.startswith("task_id,target,task_status,call_index")
    assert any(task_id in row for row in rows)


def test_export_to_file_writes_and_reports(tmp_path: Path, capsys):
    out, task_id, _json = _run_and_get_task_id(tmp_path, capsys)
    dump_path = tmp_path / "traces.jsonl"
    rc = main([
        "export", "--config", str(out),
        "--format", "json", "--out", str(dump_path),
    ])
    assert rc == 0
    err = capsys.readouterr().err
    assert "wrote 1 trace(s)" in err or "wrote " in err
    body = dump_path.read_text()
    assert task_id in body


# --- run ----------------------------------------------------------------------


def test_run_prints_live_console_ticker_by_default(tmp_path: Path, capsys):
    """`ormica run` subscribes a ConsoleObserver by default (v0.2 step 6)."""
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        brain=BrainConfig(type="mock", replies=["ok"]),
        tasks=[TaskConfig(description="hi", dept="sales")],
    )
    save_config(cfg, out)

    rc = main(["run", "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "» task" in text  # TASK_STARTED line
    assert "✓ task" in text  # TASK_DONE line


def test_run_quiet_suppresses_console_ticker(tmp_path: Path, capsys):
    """`--quiet` skips subscribing the ConsoleObserver."""
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        brain=BrainConfig(type="mock", replies=["ok"]),
        tasks=[TaskConfig(description="hi", dept="sales")],
    )
    save_config(cfg, out)

    rc = main(["run", "--config", str(out), "--quiet"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "processed=1" in text       # final summary still prints
    assert "» task" not in text         # ticker silenced
    assert "✓ task" not in text


def test_run_uses_mock_cortex_and_completes_tasks(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        brain=BrainConfig(type="mock", replies=["hello from mock"]),
        tasks=[
            TaskConfig(description="say hi", dept="sales"),
            TaskConfig(description="say hi", dept="finance"),
        ],
    )
    save_config(cfg, out)

    rc = main(["run", "--config", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "processed=2" in text
    assert "succeeded=2" in text
    assert "failed=0" in text
    assert "[ok]" in text


def test_run_unknown_target_reports_failure_and_exits_nonzero(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        tasks=[TaskConfig(description="ghost", dept="nonexistent_dept")],
    )
    save_config(cfg, out)

    rc = main(["run", "--config", str(out)])
    assert rc == 2  # nonzero == at least one failure
    out_text = capsys.readouterr().out
    assert "failed=1" in out_text
    assert "[fail]" in out_text


def test_run_missing_config_errors(capsys, tmp_path: Path):
    rc = main(["run", "--config", str(tmp_path / "nope.yaml")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_run_cortex_override_takes_precedence(tmp_path: Path, monkeypatch):
    """`--brain claude` should override the config's `type: mock`.

    We intercept the ClaudeBrain constructor so the test doesn't need
    the anthropic SDK or network.
    """
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    constructed = {}

    class FakeClaude:
        name = "claude"

        def __init__(self, *, model):
            constructed["model"] = model
            self.model = model

        def think(self, prompt, *, system=None, max_tokens=1024):
            from ormica.brain import Response
            return Response(content="from fake claude", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.ClaudeBrain", FakeClaude, raising=True)

    rc = main(["run", "--config", str(out), "--brain", "claude"])
    assert rc == 0
    assert constructed["model"] == "claude-opus-4-7"


def test_init_with_cortex_openai_writes_gpt_default(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    rc = main(["init", "Acme", "--brain", "openai", "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text())
    assert data["brain"]["type"] == "openai"
    assert data["brain"]["model"] == "gpt-4o"


def test_init_with_cortex_claude_writes_opus_default(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    rc = main(["init", "Acme", "--brain", "claude", "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text())
    assert data["brain"]["type"] == "claude"
    assert data["brain"]["model"] == "claude-opus-4-7"


def test_run_with_openai_override_uses_gpt_default_model(tmp_path: Path, monkeypatch):
    """`--brain openai` on a mock-config run picks the gpt-4o default."""
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    constructed = {}

    class FakeGPT:
        name = "openai"

        def __init__(self, *, model):
            constructed["model"] = model
            self.model = model

        def think(self, prompt, *, system=None, max_tokens=1024):
            from ormica.brain import Response

            return Response(content="from fake gpt", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.GPTBrain", FakeGPT, raising=True)

    rc = main(["run", "--config", str(out), "--brain", "openai"])
    assert rc == 0
    assert constructed["model"] == "gpt-4o"


def test_run_with_openai_in_config_respects_configured_model(tmp_path: Path, monkeypatch):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        brain=BrainConfig(type="openai", model="gpt-4o-mini"),
        tasks=[TaskConfig(description="hi")],
    )
    save_config(cfg, out)

    constructed = {}

    class FakeGPT:
        name = "openai"

        def __init__(self, *, model):
            constructed["model"] = model
            self.model = model

        def think(self, prompt, *, system=None, max_tokens=1024):
            from ormica.brain import Response

            return Response(content="ok", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.GPTBrain", FakeGPT, raising=True)

    rc = main(["run", "--config", str(out)])
    assert rc == 0
    assert constructed["model"] == "gpt-4o-mini"


# --- --async flag -------------------------------------------------------------


def test_run_async_uses_async_mock_cortex(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        brain=BrainConfig(type="mock", replies=["from async mock"]),
        tasks=[
            TaskConfig(description="a"),
            TaskConfig(description="b"),
            TaskConfig(description="c"),
        ],
    )
    save_config(cfg, out)

    rc = main(["run", "--config", str(out), "--async"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "processed=3" in text
    assert "succeeded=3" in text


def test_run_async_with_concurrency_flag_passes_through(tmp_path: Path, monkeypatch):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    received = {}

    real_arun_attr = "ormica.core.Ormica.arun"
    original_arun = None

    from ormica import Ormica

    original_arun = Ormica.arun

    async def spy_arun(self, *, brain, max_tasks=100, concurrency=5,
                       on_task_start=None, on_task_done=None):
        received["concurrency"] = concurrency
        return await original_arun(
            self,
            brain=brain,
            max_tasks=max_tasks,
            concurrency=concurrency,
            on_task_start=on_task_start,
            on_task_done=on_task_done,
        )

    monkeypatch.setattr(real_arun_attr, spy_arun, raising=True)

    rc = main(["run", "--config", str(out), "--async", "--concurrency", "7"])
    assert rc == 0
    assert received["concurrency"] == 7


def test_run_async_with_claude_override_builds_async_claude(tmp_path: Path, monkeypatch):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    constructed = {}

    class FakeAsyncClaude:
        name = "async-claude"

        def __init__(self, *, model):
            constructed["model"] = model
            self.model = model

        async def think(self, prompt, *, system=None, max_tokens=1024):
            from ormica.brain import Response

            return Response(content="claude says hi", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.AsyncClaudeBrain", FakeAsyncClaude, raising=True)

    rc = main(["run", "--config", str(out), "--brain", "claude", "--async"])
    assert rc == 0
    assert constructed["model"] == "claude-opus-4-7"


def test_run_async_with_openai_override_builds_async_gpt(tmp_path: Path, monkeypatch):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    constructed = {}

    class FakeAsyncGPT:
        name = "async-openai"

        def __init__(self, *, model):
            constructed["model"] = model
            self.model = model

        async def think(self, prompt, *, system=None, max_tokens=1024):
            from ormica.brain import Response

            return Response(content="gpt says hi", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.AsyncGPTBrain", FakeAsyncGPT, raising=True)

    rc = main(["run", "--config", str(out), "--brain", "openai", "--async"])
    assert rc == 0
    assert constructed["model"] == "gpt-4o"


def test_run_sync_default_when_async_flag_absent(tmp_path: Path):
    """Without --async, the sync code path runs (regression guard)."""
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    rc = main(["run", "--config", str(out)])
    assert rc == 0


# --- colonies -----------------------------------------------------------------


def test_colonies_command_lists_registered(capsys):
    rc = main(["colonies"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "business" in text
    assert "supply_chain" in text


# --- parser sanity ------------------------------------------------------------


def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_rejects_unknown_subcommand(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["bogus"])


# --- OpenAI-compatible providers via UniversalBrain --------------------------


def test_init_with_ollama_writes_llama32_default(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    rc = main(["init", "Acme", "--brain", "ollama", "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text())
    assert data["brain"]["type"] == "ollama"
    assert data["brain"]["model"] == "llama3.2"


def test_init_with_openrouter_writes_default_model(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    rc = main(["init", "Acme", "--brain", "openrouter", "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text())
    assert data["brain"]["type"] == "openrouter"
    assert data["brain"]["model"] == "anthropic/claude-opus-4-7"


def test_init_with_groq_writes_llama70b_default(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    rc = main(["init", "Acme", "--brain", "groq", "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text())
    assert data["brain"]["model"] == "llama-3.3-70b-versatile"


def test_init_with_gemini_writes_flash_default(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    rc = main(["init", "Acme", "--brain", "gemini", "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text())
    assert data["brain"]["model"] == "gemini-2.0-flash"


def test_run_with_ollama_routes_through_universal_with_localhost_base_url(
    tmp_path: Path, monkeypatch
):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    constructed = {}

    class FakeUniversal:
        name = "universal"

        def __init__(self, *, model, base_url=None, api_key=None):
            constructed["model"] = model
            constructed["base_url"] = base_url
            self.model = model

        def think(self, prompt, *, system=None, max_tokens=1024, tools=None):
            from ormica.brain import Response
            return Response(content="local", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)

    rc = main(["run", "--config", str(out), "--brain", "ollama"])
    assert rc == 0
    assert constructed["model"] == "llama3.2"
    assert constructed["base_url"] == "http://localhost:11434/v1"


def test_run_with_groq_routes_through_universal_with_groq_base_url(
    tmp_path: Path, monkeypatch
):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    constructed = {}

    class FakeUniversal:
        name = "universal"

        def __init__(self, *, model, base_url=None, api_key=None):
            constructed["base_url"] = base_url
            self.model = model

        def think(self, prompt, *, system=None, max_tokens=1024, tools=None):
            from ormica.brain import Response
            return Response(content="groq", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)

    rc = main(["run", "--config", str(out), "--brain", "groq"])
    assert rc == 0
    assert constructed["base_url"] == "https://api.groq.com/openai/v1"


def test_run_with_gemini_builds_native_gemini_brain(tmp_path: Path, monkeypatch):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)

    constructed = {}

    class FakeGemini:
        name = "gemini"

        def __init__(self, *, model):
            constructed["model"] = model
            self.model = model

        def think(self, prompt, *, system=None, max_tokens=1024, tools=None):
            from ormica.brain import Response
            return Response(content="gemini says hi", model=self.model, tokens_used=1)

    monkeypatch.setattr("ormica.brain.GeminiBrain", FakeGemini, raising=True)

    rc = main(["run", "--config", str(out), "--brain", "gemini"])
    assert rc == 0
    assert constructed["model"] == "gemini-2.0-flash"


# --- Provider env-var resolution (Issue #7) ---------------------------------


def _make_universal_capture():
    """Build a FakeUniversal that records the api_key passed in."""
    captured: dict = {}

    class FakeUniversal:
        name = "universal"

        def __init__(self, *, model, base_url=None, api_key=None):
            captured["model"] = model
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            self.model = model

        def think(self, prompt, *, system=None, max_tokens=1024, tools=None):
            from ormica.brain import Response
            return Response(content="ok", model=self.model, tokens_used=1)

    return FakeUniversal, captured


def _save_minimal_config(tmp_path: Path) -> Path:
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(name="Acme", tasks=[TaskConfig(description="hi")])
    save_config(cfg, out)
    return out


def test_openrouter_uses_OPENROUTER_API_KEY_env(tmp_path: Path, monkeypatch):
    """OPENROUTER_API_KEY (documented var) must reach UniversalBrain."""
    out = _save_minimal_config(tmp_path)
    FakeUniversal, captured = _make_universal_capture()
    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")

    rc = main(["run", "--config", str(out), "--brain", "openrouter"])
    assert rc == 0
    assert captured["api_key"] == "sk-or-v1-test"


def test_groq_uses_GROQ_API_KEY_env(tmp_path: Path, monkeypatch):
    out = _save_minimal_config(tmp_path)
    FakeUniversal, captured = _make_universal_capture()
    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

    rc = main(["run", "--config", str(out), "--brain", "groq"])
    assert rc == 0
    assert captured["api_key"] == "gsk-test"


def test_together_uses_TOGETHER_API_KEY_env(tmp_path: Path, monkeypatch):
    out = _save_minimal_config(tmp_path)
    FakeUniversal, captured = _make_universal_capture()
    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("TOGETHER_API_KEY", "tg-test")

    rc = main(["run", "--config", str(out), "--brain", "together"])
    assert rc == 0
    assert captured["api_key"] == "tg-test"


def test_deepseek_uses_DEEPSEEK_API_KEY_env(tmp_path: Path, monkeypatch):
    out = _save_minimal_config(tmp_path)
    FakeUniversal, captured = _make_universal_capture()
    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")

    rc = main(["run", "--config", str(out), "--brain", "deepseek"])
    assert rc == 0
    assert captured["api_key"] == "ds-test"


def test_openrouter_falls_back_to_OPENAI_API_KEY_when_provider_var_unset(
    tmp_path: Path, monkeypatch
):
    """Backward compat: users who already set OPENAI_API_KEY for OpenRouter
    continue to work even without changing anything."""
    out = _save_minimal_config(tmp_path)
    FakeUniversal, captured = _make_universal_capture()
    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fallback")

    rc = main(["run", "--config", str(out), "--brain", "openrouter"])
    assert rc == 0
    assert captured["api_key"] == "sk-fallback"


def test_ollama_uses_literal_ollama_string_regardless_of_env(
    tmp_path: Path, monkeypatch
):
    """Ollama ignores auth, but the OpenAI SDK requires a non-empty key."""
    out = _save_minimal_config(tmp_path)
    FakeUniversal, captured = _make_universal_capture()
    monkeypatch.setattr("ormica.brain.UniversalBrain", FakeUniversal, raising=True)
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-be-used")
    monkeypatch.setenv("OPENROUTER_API_KEY", "should-not-be-used")

    rc = main(["run", "--config", str(out), "--brain", "ollama"])
    assert rc == 0
    assert captured["api_key"] == "ollama"


# --- dept / target aliasing (Issue #9) -------------------------------------


def test_dept_and_target_route_to_the_same_node(tmp_path: Path):
    """dept: X and target: X must produce identical Task.target on the org."""
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        tasks=[
            TaskConfig(description="via dept", dept="sales"),
            TaskConfig(description="via target", target="sales"),
        ],
    )
    save_config(cfg, out)

    config = load_config(out)
    from ormica import Ormica
    org = Ormica(config.name)
    org.plant(config.industry)
    for t in config.tasks:
        org.task(t.description, dept=t.dept or t.target, priority=t.priority)

    assert len(org.tasks) == 2
    assert org.tasks[0].target == org.tasks[1].target == "sales"


def test_dept_wins_when_both_dept_and_target_are_set(tmp_path: Path):
    """Documented precedence (docs/reference/ormica-yaml.md): dept wins."""
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        tasks=[
            TaskConfig(description="conflict", dept="sales", target="finance"),
        ],
    )
    save_config(cfg, out)

    config = load_config(out)
    from ormica import Ormica
    org = Ormica(config.name)
    org.plant(config.industry)
    for t in config.tasks:
        org.task(t.description, dept=t.dept or t.target, priority=t.priority)

    assert org.tasks[0].target == "sales"  # dept wins, not target


def test_neither_dept_nor_target_lands_at_root(tmp_path: Path):
    out = tmp_path / "ormica.yaml"
    cfg = OrmicaConfig(
        name="Acme",
        industry="business",
        tasks=[TaskConfig(description="floating")],
    )
    save_config(cfg, out)

    config = load_config(out)
    from ormica import Ormica
    org = Ormica(config.name)
    org.plant(config.industry)
    for t in config.tasks:
        org.task(t.description, dept=t.dept or t.target, priority=t.priority)

    assert org.tasks[0].target == ""  # routed to root


# --- YAML Constitutions (v0.2 step 4) ----------------------------------------


def test_load_config_parses_constitution_block(tmp_path: Path):
    """A `constitution:` block in ormica.yaml round-trips through load_config."""
    out = tmp_path / "ormica.yaml"
    out.write_text(yaml.safe_dump({
        "name": "Acme",
        "constitution": {
            "rules": [
                {"max_depth": 4},
                {"block_role": "finance"},
                "require_json",
            ],
        },
    }))
    config = load_config(out)
    assert config.constitution is not None
    assert len(config.constitution.rules) == 3


def test_save_then_load_omits_null_constitution(tmp_path: Path):
    """Default-init'd configs don't serialize `constitution: null`."""
    out = tmp_path / "ormica.yaml"
    save_config(OrmicaConfig(name="Acme"), out)
    raw = out.read_text()
    assert "constitution" not in raw


def test_save_then_load_roundtrip_preserves_constitution(tmp_path: Path):
    cfg = OrmicaConfig(
        name="Acme",
        constitution=ConstitutionConfig(rules=[{"max_depth": 4}, "require_json"]),
    )
    path = tmp_path / "ormica.yaml"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.constitution.rules == cfg.constitution.rules


def test_cli_run_enforces_constitution_from_yaml(tmp_path: Path, capsys):
    """End-to-end: a YAML-declared block_role rule denies the bad spawn at CLI run time."""
    out = tmp_path / "ormica.yaml"
    out.write_text(yaml.safe_dump({
        "name": "Acme",
        "industry": "business",
        "constitution": {
            "rules": [{"block_role": "finance"}],
        },
        "brain": {"type": "mock", "model": "mock", "replies": ["ok"]},
        "tasks": [],
    }))
    # `business` colony includes a finance department — the rule must block it.
    rc = main(["status", "--config", str(out)])
    # status exits 1 because building the org spawns the finance node, which the
    # rule now denies. The exact rc isn't the point — the failure mode is.
    text = capsys.readouterr()
    assert rc == 1 or "SpawnDenied" in text.err or "finance" in text.err.lower()


def test_cli_run_unknown_rule_name_errors_cleanly(tmp_path: Path, capsys):
    """A typo in a YAML rule name surfaces as a clear CLI error, not a stack trace."""
    out = tmp_path / "ormica.yaml"
    out.write_text(yaml.safe_dump({
        "name": "Acme",
        "constitution": {"rules": [{"max_dept": 4}]},  # typo: max_dept vs max_depth
    }))
    rc = main(["status", "--config", str(out)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "max_dept" in err
    assert "Available" in err or "available" in err
