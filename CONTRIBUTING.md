# Contributing to Ormica

Thanks for your interest in Ormica! It's early days, so contributions of all kinds are welcome.

## Ways to contribute

- **New colony agents** — build department or industry agents in `ormica/colony/`
- **LLM adapters** — add a provider in `ormica/cortex/`
- **Integrations** — connect a real-world tool in `ormica/integrations/`
- **Docs and examples** — improve `docs/` or add to `examples/`
- **Core engine** — work on `arbor`, `stigma`, `canopy`, or `mycelium`

## Development setup

```bash
git clone https://github.com/Ranzim/ormica.git
cd ormica
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Guidelines

- Keep the **core engine industry-agnostic**. Anything industry-specific belongs in a colony, never in `arbor`/`stigma`/`canopy`/`mycelium`.
- Every module name should reflect its concept (the biological metaphor).
- Add tests in `tests/` for new functionality. Use the mock LLM in `tests/mocks/` to avoid API costs.
- Run `ruff` before submitting.

## Pull requests

1. Fork the repo and create a branch
2. Make your change with tests
3. Open a PR describing what and why

We try to review quickly. Be kind, be clear.
