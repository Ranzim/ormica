# Changelog

All notable changes to Ormica will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **`UniversalBrain`** — one adapter for every OpenAI-compatible LLM endpoint. Configure with `base_url=` and `api_key=`. Covers OpenAI, Ollama (local), OpenRouter (300+ models), Groq, Together AI, DeepSeek, Mistral La Plateforme, Anyscale, Fireworks, vLLM, LM Studio, and any other OpenAI-compatible provider.
- **`GeminiBrain` / `AsyncGeminiBrain`** — native Google Gemini support behind `pip install ormica[gemini]`. Maps our `Message`/`ToolCall` types to Gemini's content blocks and function declarations.
- **Provider convenience constructors** in `ormica.brain.providers`: `ollama_brain()`, `openrouter_brain()`, `groq_brain()`, `together_brain()`, `deepseek_brain()` (plus `async_*` variants). One-liners over `UniversalBrain` with the right `base_url` baked in.
- **CLI now supports the popular providers as `--brain` shortcuts**: `mock` · `claude` · `openai` · `gemini` · `ollama` · `openrouter` · `groq` · `together` · `deepseek`. Each picks a sensible default model.
- **`docs/guides/llm-providers.md`** — single page documenting every recipe for every provider (15+ providers).
- **`[gemini]` extra** in `pyproject.toml` pulling `google-generativeai>=0.8`.
- **`[universal]` extra** as an alias for `[openai]` — semantic clarity for users picking the universal adapter.
- New tests: 17 for `UniversalBrain`, 22 for `GeminiBrain`, 8 for the provider helpers, 4 new CLI integration tests. Total suite now **361 tests** (up from 310).

### Changed
- Architectural pivot: **the brain layer is now 3 native adapters (Claude, Gemini, GPT) + 1 universal adapter (UniversalBrain) + 5 convenience helpers** — not one adapter per provider. This was the right shape: most providers have converged on OpenAI-compatible HTTP APIs, so we cover ~12 of them through one well-tested code path. Anthropic Claude and Google Gemini stay native because their wire formats are meaningfully different (content blocks, function declarations).
- `docs/architecture/03-brain.md` — adds the UniversalBrain section and a "native vs universal" guidance table.
- README install section — replaces `[ollama]` extra with `[universal]`, mentions all four primary install paths.

### Planned for v0.2
- YAML-defined Constitutions
- Soft-violation events emitted onto the EventBus
- Per-node Constitution overrides

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

[Unreleased]: https://github.com/Ranzim/ormica/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ranzim/ormica/releases/tag/v0.1.0
