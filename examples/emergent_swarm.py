"""Tiny end-to-end demo — emergent delegation under constitutional governance.

Run with no setup, no API key:

    python examples/emergent_swarm.py

What you see:

- A single root agent ("scout") is given a vague goal.
- It decides — via tool-use — to spawn 3 child agents, one per zone.
- Each spawn writes a note to shared memory (mycelium) and emits a
  pheromone signal (stigma) whose strength encodes "how promising."
- A Constitution rule caps depth to 1, so the scout's attempt to
  escalate deeper is denied at the substrate level (no LLM gymnastics).
- Output: the tree that emerged, the pheromone field that emerged,
  and the persistent notes that emerged — all from one prompt + tools.

This is what v0.1.0 actually does end-to-end. Everything below is real
Ormica API; the only thing scripted is the MockBrain's reply sequence
(so the demo is deterministic and offline). Swap MockBrain for
ClaudeBrain / GeminiBrain / ollama_brain() and the same code runs
against a real LLM, with the model deciding which zones to scout.
"""
from __future__ import annotations

from ormica import Agent, Ormica
from ormica.arbor import SpawnDenied
from ormica.brain import MockBrain, ToolCall, tool
from ormica.cortex import Constitution, Rule


# --- 1. The law of the colony ----------------------------------------------
# A hard rule on spawn: nothing deeper than depth 1 (root + one tier of zones).
constitution = Constitution(
    rules=[
        Rule(
            name="depth_cap",
            description="No agent may live deeper than depth 1.",
            check=lambda ctx: ctx["depth"] <= 1,
            stage="spawn",
        ),
    ]
)

org = Ormica("Scout HQ", owner="Founder", constitution=constitution)


# --- 2. Tools the scout can call -------------------------------------------
@tool
def delegate_zone(zone: str, intensity: float) -> str:
    """Spawn a sub-agent for one zone, write a note, mark the pheromone trail."""
    try:
        child = org.spawn(zone, role="zone_lead", task=f"Scout {zone}.")
    except SpawnDenied as exc:
        return f"DENIED by constitution: {exc}"
    org.write(f"zones/{zone}/scouted", True, by=child)
    org.emit(f"trail/{zone}", strength=intensity, by=child)
    return f"spawned {zone!r} (trail intensity {intensity})"


@tool
def escalate(target_zone: str) -> str:
    """Spawn a deep-recon agent UNDER an existing zone (one level deeper)."""
    try:
        org.spawn("deep-recon", under=target_zone, role="recon")
        return f"spawned deep-recon under {target_zone}"
    except SpawnDenied as exc:
        return f"DENIED by constitution: {exc}"


# --- 3. Scripted "decisions" — same shape a real LLM would emit ------------
brain = MockBrain(
    replies=[
        # Turn 1–3: scout delegates to three zones with different confidence.
        [ToolCall("t1", "delegate_zone", {"zone": "north", "intensity": 1.0})],
        [ToolCall("t2", "delegate_zone", {"zone": "east",  "intensity": 3.0})],
        [ToolCall("t3", "delegate_zone", {"zone": "south", "intensity": 0.5})],
        # Turn 4: scout tries to escalate — the Constitution will deny it.
        [ToolCall("t4", "escalate",      {"target_zone": "east"})],
        # Turn 5: final text answer ends the tool loop.
        "Surveyed 3 zones. East trail is strongest. Deeper recon was denied "
        "by the constitution — handing back to the operator.",
    ]
)


# --- 4. Run the scout --------------------------------------------------------
scout = Agent(org.root, brain)
response = scout.act_with_tools(
    "Survey the territory by delegating to the right zones. "
    "Use the tools available to you.",
    tools=[delegate_zone, escalate],
)


# --- 5. Show what emerged ----------------------------------------------------
def line(title: str) -> None:
    print(f"\n=== {title} ===")


line("Final tree (before: 1 node — root only)")
for node in org:
    indent = "  " * node.depth
    role = node.role or "root"
    print(f"  {indent}{node.name:14}  [{role:10}]  state={node.state.name}")

line("Pheromone trails (decay-aware, strongest first)")
for sig in org.top_signals(n=5):
    sources = ", ".join(sorted(sig.sources))
    print(f"  {sig.topic:14}  strength={sig.strength:.2f}  by={sources}")

line("Persistent mycelium notes")
for entry in org.memory.all():
    if entry.key.startswith("zones/"):
        print(f"  {entry.key:30}  value={entry.value!r}  by={entry.author}")

line("Scout's final word")
print(f"  {response.content}")

line("Audit — number of brain calls in this run")
print(f"  brain.calls = {len(brain.calls)}  (one per turn of the tool loop)")
