"""Tests for the ormica CLI."""
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from ormica.cli.config import BrainConfig, OrmicaConfig, TaskConfig, load_config, save_config
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


def test_status_with_unknown_industry_errors(tmp_path: Path, capsys):
    out = tmp_path / "ormica.yaml"
    save_config(OrmicaConfig(name="X", industry="does_not_exist"), out)
    rc = main(["status", "--config", str(out)])
    assert rc == 1
    assert "Unknown colony" in capsys.readouterr().err


# --- run ----------------------------------------------------------------------


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
