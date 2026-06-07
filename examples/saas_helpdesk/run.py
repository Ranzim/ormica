"""Run the SaaS helpdesk colony end-to-end.

    cd examples/saas_helpdesk
    python run.py

What this shows:

1. The colony YAML defines four departments (triage, billing,
   technical, escalation), each with its own Constitution rules
   attached at the template level.
2. The top-level ormica.yaml composes an org-wide Constitution on top
   (max_depth, max_tokens, block_role legal, banned_words).
3. The CLI-equivalent runtime: load config → build org → drain the
   queue. We do it in Python here so we can poke at the result
   programmatically.
4. Every think call is captured to mycelium under traces/{task_id} so
   you can later run:

       ormica trace <task_id> --config examples/saas_helpdesk/ormica.yaml

   to inspect what happened.

Run with a real brain (no scripted replies needed) by setting an env
var and editing brain.type in ormica.yaml. For example::

    export ANTHROPIC_API_KEY=...
    # in ormica.yaml: brain.type: claude  (and remove `replies:`)
    python run.py
"""
from __future__ import annotations

from pathlib import Path

from ormica.cli.config import load_config
from ormica.cli.main import _build_brain, _build_org
from ormica.observe import ConsoleObserver, TraceObserver

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "ormica.yaml"


def main() -> int:
    config = load_config(CONFIG_PATH)
    org = _build_org(config)
    brain = _build_brain(config.brain)

    # Persist trails to mycelium so `ormica trace <id>` works after this run.
    org.subscribe(TraceObserver(store=org.memory))
    # Live ticker on stdout — same observer ormica run uses by default.
    org.subscribe(ConsoleObserver())

    print(f"\n--- {config.name} ---")
    print(f"departments: {[n.name for n in org if not n.is_root]}")
    rules = list(org.constitution) if org.constitution is not None else []
    print(f"org-wide rules: {len(rules)}")
    per_node = [n for n in org if n.rules]
    print(f"per-node rules on: {[n.name for n in per_node]}\n")

    # Stage the config's tasks into the queue and drain it.
    for t in config.tasks:
        org.task(
            t.description,
            dept=t.dept or t.target,
            priority=t.priority,
        )
    result = org.run(brain=brain)

    print(
        f"\nresult: processed={result.processed} "
        f"succeeded={result.succeeded} failed={result.failed}"
    )

    # Show what's in mycelium afterwards — proof that traces persist
    # and the CLI's `ormica trace` will find them.
    trace_entries = [
        e for e in org.memory.all() if e.key.startswith("traces/")
    ]
    print(f"\npersisted traces: {len(trace_entries)}")
    if trace_entries:
        sample = trace_entries[0]
        sample_id = sample.key.split("/", 1)[1]
        print(
            f"  inspect one with: "
            f"ormica trace {sample_id} --config {CONFIG_PATH}"
        )

    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
