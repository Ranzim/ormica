"""Human-in-the-loop spawn approval — a tiny end-to-end demo.

Run with no setup, no API key::

    python examples/human_approval.py

What it shows:

- Two roles map to ROOT-risk in our canopy: ``finance`` and ``legal``.
- The first spawn (``scout``) is AUTO-risk → no prompt.
- The second spawn (``finance``) is ROOT-risk → ``ConsoleApprover``
  asks you. Type ``y`` to allow, anything else to deny.
- We then drive the same shape with a ``CallbackApprover`` and a
  scripted whitelist callback, to show the production seam without
  needing to wire a real Slack / queue.
"""
from __future__ import annotations

import io

from ormica import Ormica
from ormica.arbor import SpawnDenied
from ormica.canopy import (
    Canopy,
    CallbackApprover,
    ConsoleApprover,
    RiskLevel,
    RoleRisk,
)


def demo_console_approver() -> None:
    print("\n--- ConsoleApprover demo ---")
    canopy = Canopy(
        assessor=RoleRisk({"finance": RiskLevel.ROOT, "legal": RiskLevel.ROOT}),
        root_approver=ConsoleApprover(),
    )
    org = Ormica("Acme", policy=canopy)

    # AUTO-risk — no prompt.
    org.spawn("scout", role="scout")
    print("  spawned scout (AUTO, no prompt)")

    # ROOT-risk — prompts you on stdin.
    try:
        org.spawn("finance", role="finance")
        print("  spawned finance (ROOT-approved)")
    except SpawnDenied as exc:
        print(f"  finance denied: {exc}")


def demo_callback_approver() -> None:
    print("\n--- CallbackApprover demo (scripted callback) ---")

    decisions: list[tuple[str, str]] = []

    def whitelist_only(request, at) -> bool:
        decisions.append((request.child_name, at.name))
        return request.child_name in {"finance"}  # legal always denied

    canopy = Canopy(
        assessor=RoleRisk({"finance": RiskLevel.ROOT, "legal": RiskLevel.ROOT}),
        root_approver=CallbackApprover(whitelist_only),
    )
    org = Ormica("Acme", policy=canopy)

    org.spawn("finance", role="finance")
    print("  finance: approved by callback")
    try:
        org.spawn("legal", role="legal")
    except SpawnDenied:
        print("  legal: denied by callback")

    print(f"  callback was consulted {len(decisions)} time(s): {decisions}")


def demo_scripted_console_approver() -> None:
    """Same shape as ConsoleApprover but with scripted stdin — useful in CI."""
    print("\n--- ConsoleApprover demo (scripted stdin, for CI) ---")
    canopy = Canopy(
        assessor=RoleRisk({"finance": RiskLevel.ROOT}),
        root_approver=ConsoleApprover(
            input_stream=io.StringIO("y\n"),
            output_stream=io.StringIO(),
        ),
    )
    org = Ormica("Acme", policy=canopy)
    org.spawn("finance", role="finance")
    print("  finance approved via scripted 'y' input")


def main() -> int:
    demo_scripted_console_approver()
    demo_callback_approver()
    # Interactive demo runs last so CI runs can stop here without blocking
    # on input. Uncomment to try it locally:
    # demo_console_approver()
    print("\nFor the interactive ConsoleApprover prompt, edit main() and "
          "uncomment demo_console_approver().")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
