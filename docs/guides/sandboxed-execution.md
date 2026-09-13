# Sandboxed tool execution

Hard tasks often need an agent to **run** code, not just write it — analyze
data, execute a generated script, probe a target in a CTF. Running that against
the host process is dangerous. The sandbox runs it in a contained subprocess and
hands the agent a tool for it.

## ⚠️ Security level — read first

This **reduces blast radius**; it is **not a security jail**. It does not use
containers, namespaces, or seccomp, and it **does not block network access**.
For genuinely untrusted or adversarial code, run this *inside* a container or
VM. Treat it as "an agent's code can't trivially wreck the host or hang the
run," **not** "safe to execute malware."

## What it contains

| Measure | Effect |
|---|---|
| Wall-clock timeout | the process is killed if it runs too long |
| CPU / memory limits (POSIX) | `resource.setrlimit` in the child before exec |
| Isolated temp cwd | a fresh directory, removed after the run |
| **Minimal environment** | the parent's env is dropped — secrets/API keys in `os.environ` never reach sandboxed code |
| No shell | commands run as an argv list; nothing to inject into |
| Bounded output | stdout/stderr truncated to a cap |

## Direct use

```python
from ormica.sandbox import Sandbox, SandboxLimits

box = Sandbox(SandboxLimits(timeout_sec=5, max_memory_mb=512))

r = box.run_python("print(sum(range(100)))")
print(r.ok, r.returncode, r.stdout)   # True 0 '4950\n'

r = box.run_python("while True: pass")
print(r.timed_out)                    # True
```

`run(argv)` runs an arbitrary command with no shell:

```python
box.run(["python", "script.py", "--flag"])   # argv list, never a shell string
```

## As agent tools

Two ready-made tools; hand them to `act_with_tools`:

```python
from ormica.sandbox import python_tool, command_tool

agent.act_with_tools(
    "Compute the 20th Fibonacci number by running code.",
    tools=[python_tool()],           # exposes run_python(code)
)

agent.act_with_tools(
    "List the files the build produced.",
    tools=[command_tool()],          # exposes run_command(command)
)
```

Both return an LLM-friendly result string (`[exit=0]` / `[timed out]` plus
stdout/stderr), so the model can read the outcome and continue.

Share one configured `Sandbox` across tools to apply the same limits:

```python
box = Sandbox(SandboxLimits(timeout_sec=10))
tools = [python_tool(box), command_tool(box)]
```

## Forwarding specific environment variables

By default nothing from the parent env is visible. Forward only what you mean to:

```python
box = Sandbox(allow_env=["MY_PUBLIC_API_BASE"])   # this var passes through; secrets don't
```

## Pairs well with

- [Verification](./verification.md) — a `verifier` that runs the agent's code in the sandbox and checks it actually works (compiles / passes tests) before accepting the answer.
- [Human approvals](./human-approvals.md) — gate a `run_command` behind approval for higher-risk actions.
- [Budget governor](./budget-governor.md) — cap how many code-running agents the colony spawns.

## Hardening further

For real isolation, run the whole colony (or just the sandbox subprocess) inside
a container with no network and a read-only root, and point `Sandbox(python=...)`
at that interpreter. The measures here compose with, but do not replace, OS-level
isolation.
