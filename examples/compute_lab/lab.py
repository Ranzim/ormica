"""Ormica Compute Lab — the flagship end-to-end example.

A colony of *analyst* agents each solve a verifiable computation. The pattern
is the whole point:

    the model PROPOSES a solution  →  the cortex's verify stage GROUNDS it by
    running the code in the sandbox and checking the result against ground
    truth  →  on a mismatch it retries with the failure fed back  →  only a
    correct, executed answer is accepted.

That "propose → ground → retry" loop is what separates a plausible answer from
a *verified* one. Every quantity here is checked by actually running code in an
isolated sandbox — no trust in the model's arithmetic.

Run it::

    # offline, deterministic (no API key needed — the sandbox still runs real code)
    python examples/compute_lab/lab.py

    # with a real LLM (it writes the code itself, and must pass the sandbox)
    export ANTHROPIC_API_KEY=...        # or GEMINI_API_KEY / GOOGLE_API_KEY
    python examples/compute_lab/lab.py

    # watch it happen live in the 3D colony graph
    python examples/compute_lab/lab.py --dashboard
    #   → open http://127.0.0.1:8777/graph
"""
from __future__ import annotations

import argparse
import os
import re
import threading
import time

from ormica import Ormica
from ormica.brain import MockBrain
from ormica.cortex import verifier
from ormica.sandbox import Sandbox, SandboxLimits

# Each problem: a name, the question the agent is asked, and a *reference*
# solution used only to compute ground truth (by running it in the sandbox).
PROBLEMS = [
    (
        "prime-sum",
        "Compute the sum of all prime numbers below 100000.",
        """
n = 100000
sieve = [True] * n
sieve[0] = sieve[1] = False
for i in range(2, int(n**0.5) + 1):
    if sieve[i]:
        for j in range(i*i, n, i):
            sieve[j] = False
print(sum(i for i in range(n) if sieve[i]))
""",
    ),
    (
        "factorial-digits",
        "Compute the sum of the decimal digits of 50 factorial (50!).",
        "import math; print(sum(int(c) for c in str(math.factorial(50))))",
    ),
    (
        "collatz",
        "Compute the length of the Collatz sequence starting at 27 "
        "(count the start and the final 1).",
        """
n, c = 27, 1
while n != 1:
    n = n // 2 if n % 2 == 0 else 3 * n + 1
    c += 1
print(c)
""",
    ),
]

_SYSTEM = (
    "You are a computational analyst in a colony. Reply with ONLY a Python 3 "
    "snippet that prints the single numeric answer to the problem — no prose, "
    "no explanation, no markdown. Your code will be executed to check it."
)


def extract_code(text: str) -> str:
    """Pull code out of a possibly markdown-fenced model reply."""
    m = re.search(r"```(?:python)?\s*(.+?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def grounded(expected: str, sandbox: Sandbox):
    """A verify rule that RUNS the agent's code and checks it prints ``expected``.

    This is grounding: the answer is accepted only if executing it in the
    sandbox reproduces the ground-truth value. A wrong answer fails the rule,
    and the agent is re-prompted with the reason (verify-stage retry).
    """

    def check(ctx: dict) -> bool:
        code = extract_code(ctx["response"].content)
        return sandbox.run_python(code).stdout.strip() == expected

    return verifier(
        "grounded_by_sandbox",
        check,
        description=f"your Python must run in the sandbox and print exactly {expected}",
    )


def pick_brain():
    """A real LLM if a key is present, else a deterministic offline mock.

    The mock returns each problem's reference code, so the demo runs anywhere —
    but the sandbox still executes real code and verify still grounds it.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        from ormica.brain import ClaudeBrain

        return ClaudeBrain(), "Claude (live)"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        from ormica.brain.gemini import GeminiBrain

        return GeminiBrain(model="gemini-3.6-flash"), "Gemini (live)"

    def reply(messages):
        text = messages[-1].content
        for _name, question, ref in PROBLEMS:
            if question[:24] in text:
                return ref
        return "print('no solution')"

    return MockBrain(reply_fn=reply), "MockBrain (offline)"


def build(sandbox: Sandbox):
    """Plant a lab colony: one analyst per problem, each grounded by the sandbox."""
    org = Ormica("Ormica Compute Lab")
    from ormica.observe import TraceObserver

    org.subscribe(TraceObserver(store=org.memory))  # capture the Thought Trail
    for name, question, ref in PROBLEMS:
        expected = sandbox.run_python(ref).stdout.strip()  # ground truth, executed
        node = org.spawn(name, role="analyst")
        node.meta["system_prompt"] = _SYSTEM
        node.rules.append(grounded(expected, sandbox))       # verify → grounding
        org.task(question, target=name)
    return org


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica Compute Lab — flagship demo")
    ap.add_argument("--dashboard", action="store_true", help="serve the live 3D graph")
    ap.add_argument("--port", type=int, default=8777)
    args = ap.parse_args(argv)

    sandbox = Sandbox(SandboxLimits(timeout_sec=20))
    org = build(sandbox)
    brain, label = pick_brain()
    print(f"brain: {label}   ·   problems: {len(PROBLEMS)}\n")

    if args.dashboard:
        from ormica.dashboard import serve

        threading.Thread(target=lambda: serve(org, port=args.port), daemon=True).start()
        time.sleep(1)
        print(f"dashboard: http://127.0.0.1:{args.port}/graph\n")

    def announce(task):
        time.sleep(0.4 if args.dashboard else 0)  # let the graph breathe when watching

    result = org.run(brain=brain, on_task_start=announce)

    print("results (each verified by executing it in the sandbox):")
    for task in org.tasks:
        mark = "✓" if task.status == "done" else "✗"
        trace = org.trace_for(task.id)
        tries = len(trace.entries) if trace else 1
        detail = (task.result or task.error or "").strip().replace("\n", " ")[:60]
        print(f"  {mark} {task.target:<18} {task.status:<7} "
              f"({tries} think call(s))  {detail}")
    print(f"\n{result.succeeded}/{result.processed} verified.  "
          f"Every ✓ was executed in the sandbox and matched ground truth.")
    if args.dashboard:
        print("\ndashboard still live — Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
