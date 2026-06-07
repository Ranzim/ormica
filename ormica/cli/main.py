"""``ormica`` CLI entry point."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from .config import BrainConfig, OrmicaConfig, load_config, save_config

DEFAULT_CONFIG = Path("ormica.yaml")

# When ``init`` picks a brain type, give the config a model string that
# matches that provider so the file is runnable as-is.
_DEFAULT_MODELS = {
    "mock": "mock",
    "claude": "claude-opus-4-7",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.2",
    "openrouter": "anthropic/claude-opus-4-7",
    "groq": "llama-3.3-70b-versatile",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "deepseek": "deepseek-chat",
}


# --- command implementations ---------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"error: {out} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    config = OrmicaConfig(
        name=args.name,
        owner=args.owner,
        industry=args.industry,
        brain=BrainConfig(
            type=args.brain,
            model=_DEFAULT_MODELS[args.brain],
        ),
    )
    save_config(config, out)
    print(f"Wrote {out}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if not path.exists():
        print(
            f"error: {path} not found. Run 'ormica init <name>' first.",
            file=sys.stderr,
        )
        return 1

    config = load_config(path)
    try:
        org = _build_org(config)
        brain = _build_brain(
            config.brain, override=args.brain, async_mode=args.async_
        )
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    # Subscribe a TraceObserver so per-task Thought Trails persist to
    # mycelium under traces/{task_id}. Without persistence configured
    # they survive only for this process, but `ormica trace` can still
    # read them while the same `ormica run` invocation is in scope.
    from ormica.observe import ConsoleObserver, TraceObserver

    org.subscribe(TraceObserver(store=org.memory))
    if not args.quiet:
        org.subscribe(ConsoleObserver())

    for t in config.tasks:
        org.task(t.description, dept=t.dept or t.target, priority=t.priority)

    if args.async_:
        result = asyncio.run(
            org.arun(brain=brain, concurrency=args.concurrency)
        )
    else:
        result = org.run(brain=brain)
    print(
        f"processed={result.processed} succeeded={result.succeeded} "
        f"failed={result.failed}"
    )
    for task in org.tasks:
        mark = {"done": "[ok]", "failed": "[fail]"}.get(task.status, "[--]")
        body = task.result or task.error or ""
        target = task.target or "root"
        print(f"  {mark} [{task.priority}] {target}: {body}")
    return 0 if result.failed == 0 else 2


def cmd_status(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if not path.exists():
        print(f"error: {path} not found.", file=sys.stderr)
        return 1

    config = load_config(path)
    try:
        org = _build_org(config)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    industry = config.industry or "(none)"
    owner = config.owner or "(unset)"
    print(f"name:     {config.name}")
    print(f"owner:    {owner}")
    print(f"industry: {industry}")
    print(f"brain:   {config.brain.type} (model={config.brain.model})")
    print(f"tree ({len(org)} nodes):")
    for node in org:
        indent = "  " * node.depth
        role = node.role or "-"
        print(f"  {indent}- {node.name} [{role}]")
    print(f"tasks defined: {len(config.tasks)}")
    for t in config.tasks:
        target = t.dept or t.target or "root"
        print(f"  - [{t.priority}] {target}: {t.description}")
    return 0


def cmd_colonies(_: argparse.Namespace) -> int:
    from ormica.colony import colonies, get_colony

    for name in colonies():
        cls = get_colony(name)
        print(f"{name}: {cls.description}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Start the web dashboard. Reads from the same ormica.yaml the other commands use."""
    path = Path(args.config)
    if not path.exists():
        print(f"error: {path} not found.", file=sys.stderr)
        return 1

    config = load_config(path)
    try:
        org = _build_org(config)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    from ormica.dashboard import serve

    try:
        serve(org, host=args.host, port=args.port)
    except OSError as exc:
        print(f"error: failed to bind {args.host}:{args.port} — {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    """List the active Constitution — org-level + per-node rules."""
    path = Path(args.config)
    if not path.exists():
        print(f"error: {path} not found.", file=sys.stderr)
        return 1

    config = load_config(path)
    try:
        org = _build_org(config)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    org_rules = list(org.constitution) if org.constitution is not None else []
    if org_rules:
        print(f"org-wide rules ({len(org_rules)}):")
        for rule in org_rules:
            print(f"  - [{rule.stage}/{rule.severity}] {rule.name} — {rule.description}")
    else:
        print("org-wide rules: (none)")

    nodes_with_rules = [n for n in org if n.rules]
    if nodes_with_rules:
        print("\nper-node rules:")
        for node in nodes_with_rules:
            print(f"  {node.name} [{node.role or '-'}]:")
            for rule in node.rules:
                print(
                    f"    - [{rule.stage}/{rule.severity}] {rule.name} "
                    f"— {rule.description}"
                )
    else:
        print("\nper-node rules: (none)")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    """List stigma trails currently in shared memory, sorted by strength."""
    path = Path(args.config)
    if not path.exists():
        print(f"error: {path} not found.", file=sys.stderr)
        return 1

    config = load_config(path)
    try:
        org = _build_org(config)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    trails = org.signals.trails()
    if not trails:
        target = config.memory_db or config.memory_file or "(in-memory only)"
        print(f"no signals found. (backend: {target})")
        return 0

    print(f"{len(trails)} signal(s):")
    print(f"  {'topic':<24}  {'strength':>10}  sources")
    for s in trails[: args.top]:
        sources = ",".join(sorted(s.sources)) if s.sources else "-"
        print(f"  {s.topic:<24}  {s.strength:>10.3f}  {sources}")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Dump a stored Thought Trail for a task by id."""
    path = Path(args.config)
    if not path.exists():
        print(f"error: {path} not found.", file=sys.stderr)
        return 1

    config = load_config(path)
    try:
        org = _build_org(config)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    trace = org.trace_for(args.task_id)
    if trace is None:
        backend = config.memory_db or config.memory_file or "(in-memory only)"
        print(
            f"no trace found for task_id={args.task_id!r}. "
            f"Backend: {backend}",
            file=sys.stderr,
        )
        return 1

    print(f"task_id:     {trace.task_id}")
    print(f"target:      {trace.target or '(root)'}")
    print(f"description: {trace.description}")
    print(f"status:      {trace.status}")
    if trace.error:
        print(f"error:       {trace.error}")
    if trace.result:
        print(f"result:      {trace.result}")
    print(f"think calls: {len(trace.entries)}")
    for i, entry in enumerate(trace.entries, start=1):
        print(f"\n  [{i}] tokens={entry.tokens_used} tools={entry.tool_names or '-'}")
        if entry.system:
            print(f"      system: {_truncate(entry.system, 80)}")
        for msg in entry.messages:
            content = _truncate(str(msg.get("content", "")), 80)
            print(f"      {msg.get('role', '?'):<8} {content}")
        if entry.response_content:
            print(f"      → {_truncate(entry.response_content, 80)}")
    return 0


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# --- helpers ------------------------------------------------------------------


def _build_org(config: OrmicaConfig):
    from ormica import Ormica

    constitution = None
    if config.constitution is not None and config.constitution.rules:
        from ormica.cortex.loader import build_constitution

        constitution = build_constitution(config.constitution.rules)

    org = Ormica(
        config.name,
        owner=config.owner,
        max_depth=config.max_depth,
        memory_path=config.memory_file or None,
        memory_db=config.memory_db or None,
        constitution=constitution,
    )
    if config.industry:
        industry = config.industry
        if industry.endswith((".yaml", ".yml")) or "/" in industry or "\\" in industry:
            from ormica.colony import load_colony

            colony_cls = load_colony(industry, register=True)
            org.plant(colony_cls.name)
        else:
            org.plant(industry)
    return org


def _build_brain(
    brain_config: BrainConfig,
    *,
    override: Optional[str] = None,
    async_mode: bool = False,
):
    type_name = (override or brain_config.type).lower()
    # When overriding the type, the configured model probably belongs to the
    # old provider — fall back to the new provider's default instead.
    model = (
        _DEFAULT_MODELS.get(type_name, brain_config.model)
        if override is not None
        else brain_config.model
    )

    if type_name == "mock":
        if async_mode:
            from ormica.brain import AsyncMockBrain

            return AsyncMockBrain(replies=brain_config.replies or ["ok"])
        from ormica.brain import MockBrain

        return MockBrain(replies=brain_config.replies or ["ok"])
    if type_name == "claude":
        if async_mode:
            from ormica.brain import AsyncClaudeBrain

            return AsyncClaudeBrain(model=model or _DEFAULT_MODELS["claude"])
        from ormica.brain import ClaudeBrain

        return ClaudeBrain(model=model or _DEFAULT_MODELS["claude"])
    if type_name == "openai":
        if async_mode:
            from ormica.brain import AsyncGPTBrain

            return AsyncGPTBrain(model=model or _DEFAULT_MODELS["openai"])
        from ormica.brain import GPTBrain

        return GPTBrain(model=model or _DEFAULT_MODELS["openai"])
    # OpenAI-compatible providers route through UniversalBrain with a base_url.
    _OPENAI_COMPAT = {
        "ollama":     "http://localhost:11434/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "groq":       "https://api.groq.com/openai/v1",
        "together":   "https://api.together.xyz/v1",
        "deepseek":   "https://api.deepseek.com/v1",
    }
    # Each provider documents its own env var (see ormica/brain/providers.py).
    # Without this map the OpenAI SDK would silently fall back to
    # OPENAI_API_KEY for every provider, contradicting the docs.
    _PROVIDER_ENV_VARS = {
        "openrouter": "OPENROUTER_API_KEY",
        "groq":       "GROQ_API_KEY",
        "together":   "TOGETHER_API_KEY",
        "deepseek":   "DEEPSEEK_API_KEY",
    }
    if type_name in _OPENAI_COMPAT:
        base_url = _OPENAI_COMPAT[type_name]
        if type_name == "ollama":
            # Ollama ignores the key but the OpenAI SDK requires a non-empty
            # string. Match what ormica.brain.providers.ollama_brain does.
            api_key: Optional[str] = "ollama"
        else:
            env_var = _PROVIDER_ENV_VARS.get(type_name)
            # Prefer the provider's documented env var; fall back to
            # OPENAI_API_KEY so users who already wired things that way
            # (and the case where the provider isn't in the map) still work.
            api_key = (os.environ.get(env_var) if env_var else None) \
                or os.environ.get("OPENAI_API_KEY")
        if async_mode:
            from ormica.brain import AsyncUniversalBrain

            return AsyncUniversalBrain(
                model=model or _DEFAULT_MODELS[type_name],
                base_url=base_url,
                api_key=api_key,
            )
        from ormica.brain import UniversalBrain

        return UniversalBrain(
            model=model or _DEFAULT_MODELS[type_name],
            base_url=base_url,
            api_key=api_key,
        )
    if type_name == "gemini":
        if async_mode:
            from ormica.brain import AsyncGeminiBrain

            return AsyncGeminiBrain(model=model or _DEFAULT_MODELS["gemini"])
        from ormica.brain import GeminiBrain

        return GeminiBrain(model=model or _DEFAULT_MODELS["gemini"])
    raise ValueError(
        f"unknown brain type: {type_name!r} "
        f"(expected one of: mock, claude, openai, gemini, ollama, openrouter, groq, together, deepseek)"
    )


# --- parser + entry point -----------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ormica",
        description="Run self-organizing AI agent colonies.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a starter ormica.yaml")
    init.add_argument("name", help="Organization name")
    init.add_argument("--owner", default="", help="Owner / human-in-the-loop")
    init.add_argument(
        "--industry",
        default="business",
        help="Colony to plant (run 'ormica colonies' to list)",
    )
    init.add_argument("--out", default=str(DEFAULT_CONFIG), help="Config file path")
    init.add_argument("--force", action="store_true", help="Overwrite existing file")
    init.add_argument(
        "--brain",
        default="mock",
        choices=[
            "mock", "claude", "openai", "gemini",
            "ollama", "openrouter", "groq", "together", "deepseek",
        ],
        help="Default brain type for the new config",
    )
    init.set_defaults(func=cmd_init)

    run = sub.add_parser("run", help="Run the colony's pending tasks")
    run.add_argument("--config", default=str(DEFAULT_CONFIG))
    run.add_argument(
        "--brain",
        default=None,
        choices=[
            "mock", "claude", "openai", "gemini",
            "ollama", "openrouter", "groq", "together", "deepseek",
        ],
        help="Override the brain type from config",
    )
    run.add_argument(
        "--async",
        dest="async_",
        action="store_true",
        help="Run tasks concurrently via the async runner",
    )
    run.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent tasks when --async is set (default 5)",
    )
    run.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the live event ticker (task start/done, soft rule fires)",
    )
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="Show the org's structure and defined tasks")
    status.add_argument("--config", default=str(DEFAULT_CONFIG))
    status.set_defaults(func=cmd_status)

    col = sub.add_parser("colonies", help="List available colonies")
    col.set_defaults(func=cmd_colonies)

    dash = sub.add_parser(
        "dashboard",
        help="Start the web dashboard (stdlib-only HTTP server, view-only + live events)",
    )
    dash.add_argument("--config", default=str(DEFAULT_CONFIG))
    dash.add_argument("--port", type=int, default=8000, help="default 8000")
    dash.add_argument(
        "--host",
        default="127.0.0.1",
        help="default 127.0.0.1 (use 0.0.0.0 to expose on LAN — there is no auth)",
    )
    dash.set_defaults(func=cmd_dashboard)

    rules = sub.add_parser(
        "rules",
        help="List the active Constitution — org-level + per-node rules",
    )
    rules.add_argument("--config", default=str(DEFAULT_CONFIG))
    rules.set_defaults(func=cmd_rules)

    signals = sub.add_parser(
        "signals",
        help="List stigma trails currently in shared memory, sorted by strength",
    )
    signals.add_argument("--config", default=str(DEFAULT_CONFIG))
    signals.add_argument("--top", type=int, default=20, help="Limit to top N (default 20)")
    signals.set_defaults(func=cmd_signals)

    trace = sub.add_parser(
        "trace",
        help="Dump a stored Thought Trail for a task by id",
    )
    trace.add_argument("task_id")
    trace.add_argument("--config", default=str(DEFAULT_CONFIG))
    trace.set_defaults(func=cmd_trace)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
