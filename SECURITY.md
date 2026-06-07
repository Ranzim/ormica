# Security policy

Thanks for helping keep Ormica safe.

## Supported versions

Ormica is in early development. Until `v1.0`, **only the latest minor release** receives security fixes.

| Version | Supported |
|---|---|
| `v0.1.x` | ✅ |
| `< v0.1` | ❌ |

## Reporting a vulnerability

**Please do not file a public GitHub issue for security problems.**

If you've found a vulnerability — credential exposure, prompt-injection bypass, sandbox escape via tool execution, authentication weakness, dependency CVE, anything — report it privately. The preferred channel is GitHub Private Vulnerability Reporting:

> 🔒 **[Report a vulnerability](https://github.com/Ranzim/ormica/security/advisories/new)**

It gives you a structured form, a private discussion thread tied to the repo, and an audit trail. No GitHub account? Email the maintainer instead:

> 📧 **ormica.maintainer@gmail.com**

Include:

1. **What** — a clear description of the issue.
2. **How** — steps to reproduce (a minimal repro script is ideal).
3. **Impact** — what an attacker could do.
4. **Suggested fix** — optional, but welcome.

I aim to:

- Acknowledge your report within **3 business days**.
- Investigate and confirm within **14 days**.
- Ship a fix or mitigation within **30 days** of confirmation, or sooner for high-impact issues.
- Credit you in the release notes (unless you'd rather stay anonymous).

## Scope

Anything in this repository is in scope: the framework code (`ormica/`), tests (`tests/`), CI workflow (`.github/`), documentation (`docs/`), and the published packaging metadata (`pyproject.toml`).

**Out of scope** (report directly to the upstream vendor):
- Vulnerabilities in `anthropic`, `openai`, `pyyaml`, `pydantic`, or other third-party packages we depend on.
- Issues in the LLM providers' models themselves.

## Threat model notes

Ormica gives LLM-driven agents the ability to call Python tools, read/write shared memory, and spawn sub-agents. If you build with Ormica, you own these risks:

- **Tools you register run with your full process privileges.** A `@tool` that wraps `subprocess` is essentially a shell. Restrict accordingly.
- **The Constitution (`cortex`) is your safety net.** It enforces hard rules pre-think and on spawn. Treat your `Constitution` as production code — write it with the same care.
- **Mycelium persistence may contain prompts and partial reasoning.** Don't store secrets through `mycelium.write(...)` — they'll land in `tasks/{id}` and `traces/{id}`.
- **Single-process backends only.** `FileBackend` and `SqliteBackend` are not designed for hostile concurrent writers across processes.

These aren't framework bugs — they're inherent to the agentic-systems space — but knowing them helps you build safely.

Thanks for keeping the colony safe. 🐜
