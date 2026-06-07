# Ormica documentation

> **An Autonomous Operations Engine for self-organizing AI colonies.** Tag, ship, scale — without the chaos.

Start here if you're new to Ormica. Each page is one concept, with a code example and pointers into the source.

## 🚀 Getting started

- [**Onboarding — your first 5 minutes**](./onboarding.md) — plain-English tutorial. **Start here if you're new.**
- [Getting started](./getting-started.md) — same path, terser.
- [SaaS helpdesk example](../examples/saas_helpdesk/README.md) — production-style colony with four departments + real Constitution rules. **Read after onboarding to see it in context.**
- [**Concepts**](./concepts.md) — the three biological metaphors fused into one framework.

## 🏗️ Architecture (the four pillars)

The pitch defines **four functional pillars**. Each pillar is one or two modules.

| Pillar | Modules | Doc |
|---|---|---|
| 1. **Hierarchical Structure** (Queen → Caste → Worker) | `arbor` · `canopy` | [01-hierarchy](./architecture/01-hierarchy.md) |
| 2. **Stigmergic Signaling** (pheromones · reinforcement · decay) | `mycelium` · `stigma` | [02-signaling](./architecture/02-signaling.md) |
| 3. **Constitutional Governance** (the colony's law) | `cortex` | [04-governance](./architecture/04-governance.md) |
| 4. **Observability & Traceability** (the Thought Trail) | `observe` | [05-observability](./architecture/05-observability.md) |

The runtime layer that sits on top of the four pillars:

- [03-brain](./architecture/03-brain.md) — the pluggable thinking engine (Claude · GPT · Mock).
- [06-colony](./architecture/06-colony.md) — industries, agent templates, YAML loader.
- [07-runtime](./architecture/07-runtime.md) — Agent · Task · TaskRunner (sync + async).
- [08-facade](./architecture/08-facade.md) — the `Ormica` entry point that wires it all together.

[**📐 Full architecture overview →**](./architecture/README.md)

## 🛠️ Guides (how do I…?)

- [**Your First PR**](./guides/your-first-pr.md) — shortest path from "I want to help" to "merged." **Start here if you're contributing.**
- [**LLM providers**](./guides/llm-providers.md) — every recipe in one place: Claude, Gemini, OpenAI, Ollama (local), OpenRouter, Groq, Together, DeepSeek, vLLM, LM Studio…
- [Writing a custom colony](./guides/writing-a-colony.md) — Python *or* YAML.
- [Writing tools an agent can call](./guides/writing-tools.md) — `@tool` + tool loop.
- [Writing a Constitution](./guides/writing-a-constitution.md) — encoding business rules and hard constraints.
- [Reading the Thought Trail](./guides/reading-the-thought-trail.md) — debugging an agent's reasoning.
- [Persistence](./guides/persistence.md) — `FileBackend` vs `SqliteBackend`.
- [Async runs and multi-provider routing](./guides/async-and-routing.md) — `Router` + `org.arun`.
- [Web dashboard](./guides/dashboard.md) — view tree, signals, rules, traces; watch events live via SSE.
- [Human approvals](./guides/human-approvals.md) — `ConsoleApprover` for dev, `CallbackApprover` for Slack/web/queue.

### Integrations

- [Slack — send messages from your colony](./guides/integrations/slack.md) — incoming webhooks via stdlib, no extra deps.
- [Email — send mail via SMTP](./guides/integrations/email.md) — Gmail / SES / Postmark / Mailgun.
- [Run fully local with Ollama](./guides/integrations/ollama-local.md) — no API keys, no cloud, same Constitution + traces.

## 📖 Reference

- [CLI commands](./reference/cli.md) — `ormica init / run / status / colonies`.
- [ormica.yaml schema](./reference/ormica-yaml.md) — every field and what it does.

## 🤝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) at the root.
