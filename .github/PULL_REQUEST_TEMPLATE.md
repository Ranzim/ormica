# Pull request

<!-- Thanks for contributing to Ormica. Please fill out the sections below. -->

## What does this change?

<!-- One or two sentences. The diff covers the *how*; this covers the *what*. -->

## Why?

<!-- The problem this solves, or the value it adds. -->

## Linked issue

<!-- "Fixes #123" / "Refs #456" — or "none" if this is a small drive-by. -->

## Type

- [ ] 🌲 Pillar 1 — `arbor` / `canopy`
- [ ] 🐜 Pillar 2 — `stigma` / `mycelium`
- [ ] ⚖️ Pillar 3 — `cortex` (Constitution / Rules)
- [ ] 📡 Pillar 4 — `observe` (events / Thought Trail)
- [ ] 🧠 Brain — Mock / Claude / GPT / new provider
- [ ] 🏢 Colony — new industry / template
- [ ] 🛠️ Runtime — `agent.py` / `runtime.py`
- [ ] 💻 CLI
- [ ] 📚 Docs / examples
- [ ] 🐛 Bug fix
- [ ] 🔧 Tooling / CI

## Checklist

- [ ] Tests pass locally: `pytest` (310+ tests, ~370ms)
- [ ] Lint clean: `ruff check .`
- [ ] Docs updated if API or behaviour changed (`docs/architecture/`, `docs/guides/`, or `docs/reference/`)
- [ ] If you added a public symbol, it's exported from the module's `__init__.py`
- [ ] **Core engine stays industry-agnostic** (no business / supply-chain / healthcare logic in `arbor` / `canopy` / `mycelium` / `stigma`)
- [ ] **Brain *generates*, cortex *constrains*** — no policy decisions in `brain/`, no LLM logic in `cortex/`
- [ ] If you added a new dep, it's optional (in `[claude]` / `[openai]` / `[memory]` / `[all]` extras), not in the base install

## Screenshots / output (if applicable)

<!-- For CLI or doc changes, paste before/after output. -->

## Notes for reviewers

<!-- Anything that's load-bearing but not obvious from the diff. -->
