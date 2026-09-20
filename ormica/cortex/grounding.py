"""Grounding — verify an agent's answer against a real oracle.

The ``verify`` stage checks a response and retries on failure. *Grounding* is
verification against **ground truth from the world**, not the model's say-so:
run the code and check the output, run the test suite, ask a judge model, query
a source. An oracle returns a :class:`~ormica.cortex.CheckResult` (pass/fail +
reason + optional score); the reason is fed back to the model on retry.

    from ormica.cortex import Constitution, grounded, sandbox_oracle

    con = Constitution([grounded(sandbox_oracle(expected="42"))])
    agent.act("Return Python that prints 6*7.")   # accepted only if it prints 42

An *oracle* is any ``callable(answer_text, context) -> CheckResult | bool``.
Two batteries ship here (:func:`sandbox_oracle`, :func:`judge_oracle`); write
your own for simulators, linters, DB checks, etc.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from .rule import CheckResult, Rule

Oracle = Callable[[str, dict], Any]  # returns CheckResult | bool


def _extract_code(text: str) -> str:
    """Pull code out of a possibly markdown-fenced reply."""
    m = re.search(r"```(?:[a-zA-Z0-9_]+)?\s*(.+?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def grounded(
    oracle: Oracle,
    *,
    name: str = "grounded",
    description: str = "",
    severity: str = "hard",
    stage: str = "verify",
) -> Rule:
    """Turn an oracle into a (verify-stage) :class:`~ormica.cortex.Rule`."""

    def check(ctx: dict):
        return oracle(getattr(ctx.get("response"), "content", "") or "", ctx)

    return Rule(
        name=name,
        description=description or f"grounded check: {name}",
        check=check,
        stage=stage,
        severity=severity,
    )


def sandbox_oracle(
    *,
    expected: Optional[Any] = None,
    checker: Optional[Callable[[str], bool]] = None,
    sandbox: Any = None,
    extract: Optional[Callable[[str], str]] = None,
) -> Oracle:
    """Oracle: run the answer's Python in the sandbox and verify its output.

    - ``expected`` — the exact stdout the code must print.
    - ``checker`` — a predicate over stdout, for non-exact checks.
    - neither — just require the code to run cleanly (exit 0, no timeout).

    Reports *what actually happened* (error, timeout, or wrong value) so the
    model can fix it on retry.
    """
    from ormica.sandbox import Sandbox

    box = sandbox or Sandbox()
    ext = extract or _extract_code

    def oracle(text: str, ctx: dict) -> CheckResult:
        res = box.run_python(ext(text))
        if res.timed_out:
            return CheckResult(False, "the code timed out in the sandbox")
        if res.returncode != 0:
            return CheckResult(False, f"the code errored: {res.stderr.strip()[:200]}")
        out = res.stdout.strip()
        if checker is not None:
            ok = bool(checker(out))
            return CheckResult(ok, "" if ok else f"output {out!r} was rejected")
        if expected is not None:
            ok = out == str(expected)
            return CheckResult(ok, "" if ok else f"printed {out!r}, expected {str(expected)!r}")
        return CheckResult(True)

    return oracle


def judge_oracle(brain: Any, rubric: str, *, pass_token: str = "PASS") -> Oracle:
    """Oracle: an LLM grades the answer against ``rubric`` (LLM-as-judge).

    The judge is asked to reply ``PASS`` or ``FAIL: <reason>``; the reason
    (if any) becomes the retry feedback. Use a capable model as the judge.
    """

    def oracle(text: str, ctx: dict) -> CheckResult:
        prompt = (
            f"Grade the ANSWER against the RUBRIC. Reply exactly '{pass_token}' if it "
            f"fully satisfies the rubric, otherwise 'FAIL: <one-line reason>'.\n\n"
            f"RUBRIC: {rubric}\n\nANSWER:\n{text}"
        )
        verdict = brain.think(prompt).content.strip()
        if verdict.upper().startswith(pass_token):
            return CheckResult(True)
        return CheckResult(False, verdict.removeprefix("FAIL:").strip() or "rejected by judge")

    return oracle
