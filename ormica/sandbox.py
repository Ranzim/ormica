"""Sandboxed tool execution — run code with a bounded blast radius.

Hard tasks (data analysis, security research, code generation) often need an
agent to *run* code, not just write it. Doing that against the host process is
dangerous. This module runs code in a **subprocess** with several containment
measures, and exposes it as agent tools.

What the sandbox enforces:

- **Wall-clock timeout** — the process is killed if it runs too long.
- **Resource limits** (POSIX) — CPU seconds, address space (memory), and output
  file size, via ``resource.setrlimit`` in the child before ``exec``.
- **Isolated working directory** — a fresh temp dir, removed afterward.
- **Minimal environment** — the parent's env is *not* inherited, so secrets and
  API keys in ``os.environ`` never reach sandboxed code. Pass ``allow_env`` to
  forward specific variables.
- **No shell** — commands run as an argv list; there is no shell to inject into.
- **Bounded output** — stdout/stderr are truncated to a cap.

**Security note — read this.** This reduces blast radius; it is **not** a
security jail. It does not use containers, namespaces, or seccomp, and it does
**not block network access**. For genuinely untrusted or adversarial code
(e.g. running real exploits), run this *inside* a container or VM. Treat the
sandbox as "stops an agent's code from trivially wrecking the host or hanging
the run," not "safe to execute malware."
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional, Sequence

from ormica.brain import Tool


class SandboxError(RuntimeError):
    """Raised for sandbox setup problems (not for user-code failures)."""


@dataclass(frozen=True)
class SandboxLimits:
    """Containment limits applied to each sandbox run."""

    timeout_sec: float = 5.0
    max_memory_mb: int = 512
    max_cpu_sec: int = 5
    max_output_bytes: int = 64_000

    def __post_init__(self) -> None:
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be > 0")
        if self.max_output_bytes < 1:
            raise ValueError("max_output_bytes must be >= 1")


@dataclass
class SandboxResult:
    """The outcome of one sandbox run."""

    stdout: str
    stderr: str
    returncode: Optional[int]  # None when timed out / killed
    timed_out: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def _truncate(text: Optional[str], cap: int) -> tuple[str, bool]:
    text = text or ""
    if len(text) <= cap:
        return text, False
    return text[:cap] + f"\n...[truncated, {len(text) - cap} more bytes]", True


class Sandbox:
    """Runs code/commands in a contained subprocess."""

    def __init__(
        self,
        limits: Optional[SandboxLimits] = None,
        *,
        python: str = sys.executable,
        allow_env: Sequence[str] = (),
    ) -> None:
        self.limits = limits or SandboxLimits()
        self.python = python
        self.allow_env = tuple(allow_env)

    # --- public API ---

    def run_python(self, code: str) -> SandboxResult:
        """Run a Python snippet in isolated mode (``-I``)."""
        return self.run([self.python, "-I", "-c", code])

    def run(self, argv: Sequence[str], *, stdin: str = "") -> SandboxResult:
        """Run an argv command (no shell) under the sandbox's limits."""
        if not argv:
            raise SandboxError("argv must be non-empty")
        with tempfile.TemporaryDirectory(prefix="ormica-sbx-") as workdir:
            try:
                proc = subprocess.run(
                    list(argv),
                    cwd=workdir,
                    env=self._env(workdir),
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=self.limits.timeout_sec,
                    preexec_fn=self._preexec if os.name == "posix" else None,
                )
            except subprocess.TimeoutExpired as exc:
                out, t1 = _truncate(exc.stdout, self.limits.max_output_bytes)
                err, t2 = _truncate(exc.stderr, self.limits.max_output_bytes)
                return SandboxResult(
                    stdout=out,
                    stderr=err or "process exceeded the time limit",
                    returncode=None,
                    timed_out=True,
                    truncated=t1 or t2,
                )
            except FileNotFoundError as exc:
                raise SandboxError(f"command not found: {argv[0]!r}") from exc
            out, t1 = _truncate(proc.stdout, self.limits.max_output_bytes)
            err, t2 = _truncate(proc.stderr, self.limits.max_output_bytes)
            return SandboxResult(
                stdout=out,
                stderr=err,
                returncode=proc.returncode,
                truncated=t1 or t2,
            )

    # --- internals ---

    def _env(self, workdir: str) -> dict:
        # Minimal env — the parent's variables (and any secrets in them) are
        # deliberately dropped. HOME points at the throwaway workdir.
        env = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": workdir,
            "TMPDIR": workdir,
            "LANG": "C.UTF-8",
        }
        for name in self.allow_env:
            if name in os.environ:
                env[name] = os.environ[name]
        return env

    def _preexec(self) -> None:  # pragma: no cover - runs in the child process
        import resource

        limits = self.limits
        # Each limit is best-effort: platforms differ in what they enforce.
        for res, soft in (
            (resource.RLIMIT_CPU, limits.max_cpu_sec),
            (resource.RLIMIT_AS, limits.max_memory_mb * 1024 * 1024),
            (resource.RLIMIT_FSIZE, limits.max_output_bytes * 16),
        ):
            try:
                resource.setrlimit(res, (soft, soft))
            except (ValueError, OSError):
                pass


def _format(result: SandboxResult) -> str:
    """Render a SandboxResult as an LLM-friendly tool-result string."""
    status = (
        "timed out"
        if result.timed_out
        else f"exit={result.returncode}"
    )
    parts = [f"[{status}]"]
    if result.stdout:
        parts.append(f"--- stdout ---\n{result.stdout}")
    if result.stderr:
        parts.append(f"--- stderr ---\n{result.stderr}")
    if not result.stdout and not result.stderr:
        parts.append("(no output)")
    return "\n".join(parts)


def python_tool(sandbox: Optional[Sandbox] = None) -> Tool:
    """A ``run_python`` tool: executes Python in the sandbox, returns output."""
    box = sandbox or Sandbox()

    def run_python(code: str) -> str:
        return _format(box.run_python(code))

    return Tool(
        name="run_python",
        description=(
            "Execute a Python 3 snippet in an isolated sandbox (no network "
            "assumptions, minimal environment, time/memory limited) and return "
            "its stdout/stderr. Use print() to emit results."
        ),
        fn=run_python,
        schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source to run."}
            },
            "required": ["code"],
        },
    )


def command_tool(sandbox: Optional[Sandbox] = None) -> Tool:
    """A ``run_command`` tool: runs an argv command (no shell) in the sandbox."""
    import shlex

    box = sandbox or Sandbox()

    def run_command(command: str) -> str:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return f"[error] could not parse command: {exc}"
        if not argv:
            return "[error] empty command"
        try:
            return _format(box.run(argv))
        except SandboxError as exc:
            return f"[error] {exc}"

    return Tool(
        name="run_command",
        description=(
            "Run a shell-style command in an isolated sandbox. The command is "
            "split into arguments and run WITHOUT a shell (no pipes, globbing, "
            "or variable expansion). Time/memory limited; minimal environment."
        ),
        fn=run_command,
        schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command line, e.g. 'python script.py --flag'.",
                }
            },
            "required": ["command"],
        },
    )
