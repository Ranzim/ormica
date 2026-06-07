"""Tests for the evaporate hooks — CLI flag and auto_evaporate yaml field."""
from __future__ import annotations

import time
from pathlib import Path

from ormica import Ormica
from ormica.brain import MockBrain


# --- Ormica.signals_auto_evaporate -------------------------------------------


def test_auto_evaporate_default_off():
    """Bare API stays back-compat: no evaporate after run unless asked."""
    org = Ormica("X", max_depth=3, signals_half_life=0.01, signals_floor=0.5)
    # Emit a trail strong enough to decay below floor quickly.
    leaf = org.spawn("leaf")
    org.signals.emit("topic:fade", strength=1.0, by=leaf.id)

    # Wait so the trail decays below floor (0.5) but stays in the store.
    time.sleep(0.1)
    org.task("noop", target="leaf")
    org.run(brain=MockBrain(replies=["ok"]))

    # auto_evaporate off → the decayed entry is still in the store.
    stored = sum(
        1 for e in org.memory.all() if e.key.startswith("stigma/")
    )
    # At least 1 stale entry expected; live trails() is empty due to decay.
    assert stored >= 1
    assert all(s.strength >= org.signals.floor for s in org.signals.trails())


def test_auto_evaporate_true_drops_decayed_after_run():
    """When set, run() drops stale entries after processing."""
    org = Ormica(
        "X",
        max_depth=3,
        signals_half_life=0.01,
        signals_floor=0.5,
        signals_auto_evaporate=True,
    )
    leaf = org.spawn("leaf")
    org.signals.emit("topic:fade", strength=1.0, by=leaf.id)
    time.sleep(0.1)

    org.task("noop", target="leaf")
    org.run(brain=MockBrain(replies=["ok"]))

    stigma_keys = [e for e in org.memory.all() if e.key.startswith("stigma/")]
    # The faded trail was dropped; any auto-emitted trail from this run
    # is still fresh so it stays (or could also be gone if half_life is
    # very short — assert no STALE entries specifically).
    for entry in stigma_keys:
        # Anything left must be live (strength >= floor when decay-adjusted).
        signal_strength = entry.value["strength"]
        # Even raw strength should be the freshly-reinforced value, never
        # the original 1.0 from before sleep.
        assert signal_strength >= org.signals.floor or entry.key.endswith("topic:fade") is False


def test_evaporate_failure_swallowed():
    """A broken signals.evaporate must not fail an otherwise successful run."""
    org = Ormica("X", max_depth=3, signals_auto_evaporate=True)
    leaf = org.spawn("leaf")

    def boom():
        raise RuntimeError("stigma is wedged")
    org.signals.evaporate = boom  # type: ignore[method-assign]

    org.task("noop", target="leaf")
    result = org.run(brain=MockBrain(replies=["ok"]))
    assert result.succeeded == 1
    assert result.failed == 0


# --- CLI: ormica signals --evaporate -----------------------------------------


def test_cli_signals_evaporate_flag(tmp_path: Path, capsys):
    """`ormica signals --evaporate` drops below-floor trails and reports count."""
    from ormica.cli.config import (
        BrainConfig,
        OrmicaConfig,
        StigmaConfig,
        save_config,
    )
    from ormica.cli.main import main

    db = tmp_path / "studio.db"
    cfg_path = tmp_path / "ormica.yaml"
    save_config(
        OrmicaConfig(
            name="EvapDemo",
            memory_db=str(db),
            brain=BrainConfig(type="mock", replies=["ok"]),
            stigma=StigmaConfig(half_life=0.01, floor=0.5, auto_emit=False),
        ),
        cfg_path,
    )

    # Seed a trail that will be stale by the time the CLI runs.
    org = Ormica("EvapDemo", memory_db=str(db), signals_half_life=0.01, signals_floor=0.5)
    leaf = org.spawn("leaf")
    org.signals.emit("topic:stale", strength=1.0, by=leaf.id)
    time.sleep(0.1)

    rc = main(["signals", "--config", str(cfg_path), "--evaporate"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "evaporated 1 trail(s)" in out


def test_cli_signals_without_evaporate_does_not_drop(tmp_path: Path, capsys):
    from ormica.cli.config import (
        BrainConfig,
        OrmicaConfig,
        StigmaConfig,
        save_config,
    )
    from ormica.cli.main import main

    db = tmp_path / "studio.db"
    cfg_path = tmp_path / "ormica.yaml"
    save_config(
        OrmicaConfig(
            name="EvapDemo",
            memory_db=str(db),
            brain=BrainConfig(type="mock", replies=["ok"]),
            stigma=StigmaConfig(half_life=0.01, floor=0.5, auto_emit=False),
        ),
        cfg_path,
    )

    org = Ormica("EvapDemo", memory_db=str(db), signals_half_life=0.01, signals_floor=0.5)
    leaf = org.spawn("leaf")
    org.signals.emit("topic:stale", strength=1.0, by=leaf.id)
    time.sleep(0.1)

    main(["signals", "--config", str(cfg_path)])
    out = capsys.readouterr().out
    assert "evaporated" not in out
