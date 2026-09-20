# Changelog

All notable changes to Ormica will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Typed artifacts** — schema-checked structured results, so one agent's output
  can be another's input without fragile re-parsing. `ArtifactType(name, fields)`
  declares a shape with plain Python types (nesting, `required=`, `allow_extra=`
  supported, no pydantic dependency); `.parse()` extracts JSON from a chatty /
  fenced reply, validates, and returns an `Artifact(kind, data, meta)` that
  serializes (`to_record` / `from_record`) like tasks and nodes. Integrates with
  grounding: `cortex.artifact_oracle(type)` makes a verify-stage oracle that
  feeds the exact validation problems back to the model on retry, so malformed
  structured output self-corrects.
- **Typed results flow between tasks** — declare a task's output contract with
  `org.task(..., produces=ArtifactType)`: the runner validates the answer into
  `task.artifact` (a parse failure fails the task; pair with
  `grounded(artifact_oracle(T))` for auto-retry), the artifact persists in the
  `tasks/{id}` record, and DAG dependents receive the upstream artifact as
  labeled JSON instead of re-parsing prose. Untyped tasks are unchanged — text
  still flows as before.
- **Persistent agent tree** — checkpoint and restore the colony's emergent
  structure. `Ormica.save_tree()` serializes every node's identity, lineage,
  state, and JSON-safe `meta` to one atomic mycelium record (`arbor/tree`);
  `Ormica.load_tree()` rebuilds `self.tree` in place in a fresh process,
  keeping the live policy and observation hooks. Backed by `Node.to_record` /
  `Node.from_record` and `Tree.snapshot` / `Tree.restore`. Policy, per-node
  rules, and observers are runtime wiring, re-supplied on rebuild rather than
  persisted. With a durable backend (sqlite/file), a colony survives a restart
  with its structure intact — the prerequisite for distributed execution.

## [0.5.0] — 2026-09-20

Grounding, recall, and native async: agents can now check their answers against
the real world, pull relevant memory in automatically, and run async tools
without blocking. Everything is additive; existing APIs are unchanged.

### Added

- **Grounding framework (`cortex`)** — verify a response against a real oracle,
  not the model's say-so. `grounded(oracle)` turns any
  `callable(answer, ctx) -> CheckResult | bool` into a verify-stage rule; the
  oracle's reason is fed back on retry. Two batteries ship: `sandbox_oracle`
  (run the answer's Python and check stdout via `expected=` / `checker=`, with
  markdown-fence extraction and clean error/timeout reporting) and
  `judge_oracle` (LLM-as-judge against a rubric). New `CheckResult(ok, reason,
  score)` dataclass; `Rule.evaluate` accepts a `CheckResult` or a bool.
- **Auto-RAG (`Agent(auto_recall=k)`)** — an agent automatically recalls the *k*
  most relevant memories for the incoming prompt and prepends them to the system
  context, so semantic memory feeds reasoning without a manual `recall_relevant`
  call. Configurable per node via `node.meta["auto_recall"]`.
- **Native async tools** — `act_with_tools` awaits coroutine tools directly and
  offloads sync tools to a thread (`asyncio.to_thread`) via `_run_tool_async`,
  so slow I/O tools no longer block the event loop. The sync tool path guards
  against being handed an async tool.

## [0.4.0] — 2026-09-20

Engine hardening: make the colony self-organizing at runtime, survive real LLMs,
and verify what tool-using agents actually do.

### Added

- **Recursive delegation** — an agent facing a task too big spawns sub-agents to
  handle pieces, and those sub-agents can delegate further, recursively, until
  the depth cap. `DelegationBuilder` + the `delegate` tool + `Ormica.solve()`.
  Bounded by depth, fan-out (`max_subtasks`), and the colony's own spawn policy /
  `BudgetGovernor` — planner + spawn + run unified into one recursive primitive.
- **`RetryingBrain` / `AsyncRetryingBrain`** — wrap any brain with bounded
  exponential backoff + jitter on transient API errors (rate limits, 5xx,
  timeouts); non-transient errors (auth, 400) re-raise immediately. Provider-
  agnostic (`default_is_transient`).

### Fixed

- **Verify/grounding now runs in `act_with_tools`** — the verify-retry loop
  previously ran only in `act()`, so tool-using agents (the main real-work path)
  skipped verification. The tool loop's final response is now verified, with
  feedback-and-retry up to `max_verify_attempts`.

### Changed

- CI: bumped GitHub Actions (checkout, setup-python, artifacts, codeql,
  scorecard, gh-release, pypi-publish).

## [0.3.0] — 2026-09-15

The complex-task release: the engine gains the pieces needed to plan, coordinate,
execute, verify, and observe genuinely hard multi-agent work — plus a live 3D
dashboard to watch it happen. Everything is additive; existing APIs are unchanged.

### Added

- **Semantic memory** — relevance recall on top of the mycelium storage seam.
  `SearchableBackend` (`Backend` + `search`) with `Match` results; `Embedder`
  protocol; `HashingEmbedder` (zero-dep default) and `SentenceTransformerEmbedder`
  (behind the `[memory]` extra); `InMemorySemanticBackend` and a persistent
  `ChromaBackend`; `Mycelium.search` / `Scope.search` / `Agent.recall_relevant`.
- **Verify stage (`cortex`)** — a corrective counterpart to `post`: a `verify`
  rule checks the response and, on hard failure, re-prompts with the reason and
  retries up to `max_verify_attempts`, then raises `VerificationFailed`.
  Factories `must_match` / `must_contain` / `must_be_json` and the `verifier()`
  escape hatch (domain checks, LLM-as-judge, sandbox grounding). Emits
  `verify.retry` / `verify.failed`.
- **Planner** — `Planner`/`AsyncPlanner` decompose a goal into a dependency-aware
  `Plan` of subtasks (structured JSON, cycle detection, bounded recursion,
  routing). `Ormica.plan()` / `enqueue_plan()`.
- **Parallel DAG execution** — `Task.depends_on` + `AsyncDagRunner`: runs the
  plan's graph with max safe parallelism, skips downstream of failures, and
  passes each prerequisite's result into the dependent's prompt.
  `Ormica.arun_dag()`.
- **Direct messaging (`postbox`)** — addressed agent-to-agent messages over the
  mycelium: `Postbox`, `Message`, agent/facade shortcuts, and an LLM-facing
  `send_message` tool (bounded recipients, rate limit) with colony-YAML support.
- **Durable, resumable runs** — the task queue is checkpointed to mycelium;
  `Ormica.load_tasks()` / `Ormica.resume()` re-run whatever didn't finish.
- **Spawn-time budget/cost governor** — `canopy.BudgetGovernor` (a `SpawnPolicy`)
  caps `max_agents` / `max_spawns` / shared `TokenBudget`. `Ormica(budget=…,
  spawn_governor=…)`.
- **Sandboxed tool execution** — `Sandbox` runs code/argv in a subprocess with a
  timeout, POSIX resource limits, isolated cwd, minimal env, and no shell;
  `python_tool()` / `command_tool()`.
- **Human-in-the-loop action gates** — `approval.require_approval()` wraps a
  tool so a human approves high-risk calls (fail-closed; optional `when`
  predicate); `Console`/`Callback` approvers.
- **Per-node custom tools** — `Ormica.give_tools()` hands arbitrary tools to a
  node's agent via the runner.
- **First-party GitHub integration** — `ormica.integrations.data.github` (five
  `@tool`s via the `gh` CLI, no new dependency).
- **Live 3D dashboard** — a dependency-free `/graph` view of the running colony
  (force-directed 3D, ant-colony naming, filters, click-to-reveal, live log),
  fed by new activity events: `node.spawned` / `node.pruned` / `memory.write` /
  `memory.read`.
- **Flagship example** — `examples/compute_lab`: a colony whose answers are
  grounded by executing them in the sandbox and verified with retry.

### Fixed

- CI is deterministic again: pinned the ruff rule set (`[tool.ruff.lint]`)
  so a ruff version bump can't silently change what lint enforces.

## [0.2.0] — 2026-06-07

Cortex matures, the CLI gets a face, supply chain hardens. Every roadmap row for v0.2 plus the UX scaffolding to ship it credibly.

### Added — Cortex

- **Post-stage rule enforcement** (#24) — `Rule(stage="post")` was documented but dead in v0.1; `Agent.act` and `Agent.act_with_tools` (sync + async) now call `constitution.enforce(...stage="post")` after each successful `brain.think`, with `response` added to the context. For `act_with_tools`, post fires only on the final text response — never on intermediate tool-use turns. Hard violations raise `RuleViolation` and mark the node `FAILED`; the response never leaves the agent. Soft violations emit `RULE_SOFT_VIOLATION` with `stage="post"`, matching the pre-stage pattern.
- **Standard rule library** in `ormica.cortex.rules` (#25) — ten ready-made `Rule` factories covering the most common production needs:
  - Spawn: `max_depth(n)` · `block_role(role)` · `no_child_name(name)` · `unique_role_in_subtree(role)`
  - Pre: `max_tokens(n)` · `block_prompt_pattern(pattern)` · `min_task_description(n)`
  - Post: `banned_words(words)` · `max_response_tokens(n)` · `min_response_length(n)` · `require_json()`
- **Per-node rule overrides** (#26) — `Node.rules: list` field; rules cascade down the subtree, so a rule on a department applies to every descendant and a rule on root behaves like an org-wide Constitution. Per-node rules work without an org Constitution — `Ormica.__init__` installs an empty `ConstitutionPolicy` by default so spawn rules still cascade.
- **YAML Constitutions** (#27) — `ormica.cortex.loader.build_rule` / `build_constitution` translate declarative specs into `Rule` objects. New `constitution:` block in `ormica.yaml` and per-template `rules:` field in colony YAML. Unknown rule names raise a clear `ValueError` listing what's available. Registry of nameable factories: `ormica.cortex.loader.RULE_FACTORIES`.

### Added — CLI

- **`ormica rules`** (#28) — list the active Constitution (org-wide + per-node), each rule's stage, severity, and description.
- **`ormica signals`** (#28) — list stigma trails currently in shared memory, sorted by strength, with sources.
- **`ormica trace <task_id>`** (#28) — dump a stored Thought Trail for a task, with token counts and per-think-call message history. Backed by `org.trace_for()` which reads from `mycelium['traces/{id}']`.
- **Live event ticker on `ormica run`** (#29) — new `ConsoleObserver` subscribes by default. Prints one symbol-prefixed line per task start/done/failed and per soft rule fire as the colony works. `--quiet` suppresses; the final `processed=/succeeded=/failed=` summary always prints.
- **`cmd_run` persists Thought Trails** (#28) — auto-subscribes `TraceObserver(store=org.memory)` so `ormica trace` actually has data after a run.

### Added — Supply chain & infrastructure

- **OpenSSF Scorecard workflow** (#22) — weekly + on-push analysis, publishes to securityscorecards.dev, SARIF uploaded to GitHub Code Scanning.
- **CI hardening** (#18) — every third-party Action pinned to a full commit SHA with `# vX.Y.Z` comments; `ci.yml` gets `permissions: contents: read` and a `concurrency:` block that cancels superseded PR runs.
- **GitHub Private Vulnerability Reporting** is now the preferred channel; `SECURITY.md` restructured with email as fallback. Maintainer contact moved off personal Gmail to a project-scoped forwarder (#21).
- **README polish** (#23) — accurate test counts, dynamic CI / CodeQL / Scorecard badges, security callout near the top, roadmap reflects what's shipped.

### Changed

- `Rule` docstring lists the full context schema for each stage (spawn / pre / post) — was inferred from examples in v0.1.
- `writing-a-constitution.md` gains stage-by-stage table, "block disallowed response content" pattern, per-node rules section, YAML Constitutions section, and standard rule library section.
- `docs/concepts.md` (#30) — the "random forest" framing now reads as conceptual intuition; the single-tree-per-Ormica implementation is stated explicitly; a Forest abstraction is called out as roadmap territory.

### Fixed

- `Rule(stage="post")` no longer silently does nothing (#24).
- Spawn-stage Constitution rules now receive `role` and `task_text` in context (closes #5).
- Pre-stage rule context no longer collides Node.task string with the runtime Task object — split into `task_text` (string) and `task` (runtime `Task` or `None`) (closes #6).
- `ormica status` reports `tasks defined: N`, not the misleading `tasks queued: N` (closes #10).
- `tests/test_stigma.py::test_nodes_can_emit_via_their_id` no longer flakes on slow CI runners (#19).

### Test coverage

- **455 tests across 22 files**, all green in ~450ms.
- New test files: `test_cortex_rules.py`, `test_cortex_per_node_rules.py`, `test_cortex_loader.py`.

### Migration notes

- **`SpawnPolicy.allow` is widened.** Implementations must accept `*, role: str = "", task: str = ""` kwargs. Built-in `AllowAllPolicy`, `ConstitutionPolicy`, and canopy `Policy` already do; if you have a custom policy, add `**_` (one-liner) to absorb the new kwargs.
- **Pre-stage `ctx["task"]` semantics changed.** It was the `Node.task` string; it's now the runtime `Task` object (or `None` when an `Agent` is driven directly). The string lives under `ctx["task_text"]`. Code that wrote `ctx["task"].description` now works; code that read `ctx["task"]` expecting a string should switch to `ctx["task_text"]`.

## [0.1.1] — 2026-06-06

Brain layer pivot: 3 native adapters + 1 universal adapter + 5 helpers cover ~12 providers through one well-tested code path.

### Added

- **`UniversalBrain`** — one adapter for every OpenAI-compatible LLM endpoint. Configure with `base_url=` and `api_key=`. Covers OpenAI, Ollama (local), OpenRouter (300+ models), Groq, Together AI, DeepSeek, Mistral La Plateforme, Anyscale, Fireworks, vLLM, LM Studio, and any other OpenAI-compatible provider.
- **`GeminiBrain` / `AsyncGeminiBrain`** — native Google Gemini support behind `pip install ormica[gemini]`. Maps our `Message`/`ToolCall` types to Gemini's content blocks and function declarations.
- **Provider convenience constructors** in `ormica.brain.providers`: `ollama_brain()`, `openrouter_brain()`, `groq_brain()`, `together_brain()`, `deepseek_brain()` (plus `async_*` variants). One-liners over `UniversalBrain` with the right `base_url` baked in.
- **CLI provider shortcuts** under `--brain`: `mock` · `claude` · `openai` · `gemini` · `ollama` · `openrouter` · `groq` · `together` · `deepseek`. Each picks a sensible default model.
- **`docs/guides/llm-providers.md`** — single page documenting every recipe for every provider (15+ providers).
- **`[gemini]` extra** in `pyproject.toml` pulling `google-generativeai>=0.8`.
- **`[universal]` extra** as an alias for `[openai]` — semantic clarity for users picking the universal adapter.
- **Soft-violation events** (#4) — `Agent._enforce_constitution` now captures the soft list returned by `Constitution.enforce` and emits one `RULE_SOFT_VIOLATION` event per soft fire. Previously these fired invisibly.
- New tests: 17 for `UniversalBrain`, 22 for `GeminiBrain`, 8 for the provider helpers, 4 new CLI integration tests. Total suite **361 tests** (up from 310 in v0.1.0).

### Changed

- Architectural pivot: **the brain layer is 3 native adapters (Claude, Gemini, GPT) + 1 universal adapter (UniversalBrain) + 5 convenience helpers** — not one adapter per provider. Most providers have converged on OpenAI-compatible HTTP APIs, so one well-tested code path covers ~12 of them. Anthropic Claude and Google Gemini stay native because their wire formats are meaningfully different (content blocks, function declarations).
- `docs/architecture/03-brain.md` — adds the UniversalBrain section and a "native vs universal" guidance table.
- README install section — replaces `[ollama]` extra with `[universal]`, mentions all four primary install paths.

### Fixed

- `GeminiBrain` no longer passes the unsupported `system_instruction=` kwarg to the genai SDK (#3).
- `Ormica()` raises a clear `ValueError` when both `memory_db=` and `memory_path=` are set, instead of silently dropping `memory_path` (closes #8).
- `ormica run --brain openrouter` now honors `OPENROUTER_API_KEY` and falls back to `OPENAI_API_KEY` only as a last resort (closes #7).

---

## [0.1.0] — 2026-06-05

Initial public release. All four functional pillars + runtime + CLI working end-to-end.

### Added

#### Pillar 1 — Hierarchical Structure
- `arbor` — `Tree`, `Node`, `Branch`, `SpawnPolicy` protocol. Trees grow to N depth with a configurable cap.
- `canopy` — permission chain with `AUTO` / `CHAIN` / `ROOT` risk levels. Wraps as a `SpawnPolicy`.

#### Pillar 2 — Stigmergic Signaling
- `mycelium` — shared KV store with `Backend` protocol and three implementations:
  - `InMemoryBackend` (default, RAM only)
  - `FileBackend` (atomic JSON via write-to-`.tmp` + `os.replace`)
  - `SqliteBackend` (WAL journal mode, O(1) writes, async-safe)
- `stigma` — pheromone trails layered on top of mycelium. Exponential half-life decay, lazy evaluation, `evaporate` for cleanup.

#### Pillar 3 — Constitutional Governance
- `cortex` — `Rule`, `Constitution`, `Violation`, `RuleViolation`. Three stages (`pre`, `post`, `spawn`), two severities (`hard`, `soft`).
- `ConstitutionPolicy` — wraps a Constitution as a `SpawnPolicy`, composes with canopy.

#### Pillar 4 — Observability + Thought Trail
- `observe` — `Event`, `EventBus`, `Observer` protocol.
- Built-in observers: `LogObserver`, `CounterObserver`, `CollectObserver`.
- `TraceObserver` aggregates per-task reasoning into `Trace` / `TraceEntry`; optionally persists to mycelium under `traces/{id}`.
- `Ormica.trace_for(task_id)` queryable from in-memory or persistent storage.

#### Runtime
- `brain` — LLM seam with `Brain` / `AsyncBrain` protocols.
  - `MockBrain` / `AsyncMockBrain` (no SDK required, scripted replies + scripted tool calls).
  - `ClaudeBrain` / `AsyncClaudeBrain` (Anthropic SDK, behind `[claude]` extra).
  - `GPTBrain` / `AsyncGPTBrain` (OpenAI SDK, behind `[openai]` extra).
  - `Router` for per-node brain selection (`by_name` → `by_role` → `default`).
  - `TokenBudget` + `BudgetExhausted`.
  - `Tool` + `@tool` decorator with auto-schema from type hints; `act_with_tools` multi-turn loop with `max_iterations` cap.
- `Agent` / `AsyncAgent` — bridge Node + Brain + Memory + Signals + Constitution + observability.
- `Task` + `TaskRunner` + `AsyncTaskRunner`. Priority bands (`high` → `normal` → `low`) sequentially; same-band tasks fan out concurrently via `asyncio.Semaphore`.

#### Industries
- `colony` — `AgentTemplate` + `Colony` base classes, name-based registry.
- Bundled colonies: `business` (ops/sales/marketing/finance), `supply_chain` (procurement/warehouse/logistics/quality).
- `load_colony(path, register=True)` — declarative YAML colony loader.

#### Facade
- `Ormica` — single import wires everything. Accepts `constitution=`, `policy=`, `memory=` / `memory_path=` / `memory_db=`, `signals_half_life=`.
- Sugar methods: `org.task / run / arun / plant / add / spawn / find / prune / write / read / emit / sense / top_signals / scope / subscribe / trace_for`.

#### CLI
- `ormica init` — write starter `ormica.yaml`.
- `ormica run` — drain the queue (sync). `--async --concurrency N` for parallel.
- `ormica status` — show tree + queued tasks (no execution).
- `ormica colonies` — list registered colonies.
- `--brain {mock,claude,openai}` overrides config and picks matching default model.
- Industry field auto-detects path-like YAML colony files.

#### Documentation
- `docs/README.md` — onboarding map and table of contents.
- `docs/concepts.md` — Computational Stigmergy explained.
- `docs/getting-started.md` — 5-minute Python + CLI tour.
- `docs/architecture/` — 9 pages (overview + 4 pillars + brain + colony + runtime + facade).
- `docs/guides/` — 6 task-focused how-tos (writing colonies, tools, constitutions, traces, persistence, async).
- `docs/reference/` — CLI commands + `ormica.yaml` schema.
- README rewritten as an "Autonomous Coordination Engine" pitch with mermaid diagrams (hero colony, pillar map, permission sequence, signal field, state machine).
- `CONTRIBUTING.md` revised as a where-to-put-what matrix.
- This `CHANGELOG.md`, plus `CODE_OF_CONDUCT.md` and `SECURITY.md`.

### Test coverage
- **310 tests across 18 files**, all green in ~370ms.
- Provider SDKs are not required for CI — adapters use injected fake clients.

### Naming convention finalized
- LLM seam is `brain` (was `cortex` in early drafts).
- `cortex` is reserved for governance — the colony's law. Brain *generates*; cortex *constrains*.

---

[Unreleased]: https://github.com/Ranzim/ormica/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/Ranzim/ormica/releases/tag/v0.5.0
[0.4.0]: https://github.com/Ranzim/ormica/releases/tag/v0.4.0
[0.3.0]: https://github.com/Ranzim/ormica/releases/tag/v0.3.0
[0.2.0]: https://github.com/Ranzim/ormica/releases/tag/v0.2.0
[0.1.1]: https://github.com/Ranzim/ormica/releases/tag/v0.1.1
[0.1.0]: https://github.com/Ranzim/ormica/releases/tag/v0.1.0
