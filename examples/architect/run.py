"""Ormica Architect — a colony that designs a real software architecture.

This is the "use it on a genuinely hard task" example. A lead architect spawns
specialist agents (services, data, infrastructure, security); each — driven by a
**real LLM** — analyses the system, and the lead **synthesises** their notes into
a single, schema-checked :class:`~ormica.ArtifactType` describing the whole
architecture (components, how they connect, data stores, risks).

Two engine strengths carry the weight:

  • **a colony, not one prompt** — separate specialists reason about their slice,
    so the design has real breadth instead of one model's first idea.
  • **typed + grounded output** — the final spec must parse and validate against
    the ``architecture`` type; if the model emits malformed JSON, the verify
    stage feeds the exact problem back and it retries until it's right.

The result is a structured artifact you can act on — printed here, saved to
``architecture.json``, and rendered as a diagram (see the README for the Figma
step).

Run it::

    export GEMINI_API_KEY=...            # real design, from Gemini
    python examples/architect/run.py "a ride-hailing platform at 10M users"

    python examples/architect/run.py     # no key → offline MockBrain (canned demo)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ormica import ArtifactType, Ormica
from ormica.cortex import Constitution, artifact_oracle, grounded

# The shape every design must fit — this is what makes the output *usable*.
Architecture = ArtifactType(
    "architecture",
    {
        "system": str,
        "components": list,     # [{name, responsibility, tech}]
        "connections": list,    # [{from, to, label}]
        "data_stores": list,    # [{name, kind}]
        "risks": list,          # [str]
    },
)

SPECIALISTS = {
    "services": "the service decomposition — the main components/microservices, "
                "each one's single responsibility, and a suitable technology",
    "data": "the data & storage design — the data stores, what each holds, and why "
            "(SQL vs NoSQL vs cache vs stream)",
    "infra": "the infrastructure, scaling & reliability design — how it scales, "
             "handles load, stays available, and its biggest risks",
}

_SYNTH = (
    "You are the lead architect. Combine the specialist notes below into ONE JSON "
    "object describing the architecture of: {system}\n\n"
    "Output ONLY JSON (no prose, no markdown fences) with EXACTLY these keys:\n"
    '  "system": string,\n'
    '  "components": [{{"name":..,"responsibility":..,"tech":..}}],\n'
    '  "connections": [{{"from":..,"to":..,"label":..}}]  (from/to are component names),\n'
    '  "data_stores": [{{"name":..,"kind":..}}],\n'
    '  "risks": [string]\n\n'
    "SPECIALIST NOTES:\n{notes}"
)


def pick_brain():
    """Real Gemini if a key is present, else an offline deterministic mock."""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        from ormica.brain.gemini import GeminiBrain
        from ormica.brain.retry import RetryingBrain

        model = os.environ.get("ORMICA_MODEL", "gemini-3.6-flash")
        # Wrap in RetryingBrain so free-tier 429s back off and retry transparently
        # instead of crashing the run. (Output size is set per-call via max_tokens.)
        brain = RetryingBrain(GeminiBrain(model=model), max_retries=6, base_delay=3, max_delay=65)
        return brain, f"Gemini ({model}, auto-retry)"

    # Offline fallback: specialists return a note; the lead returns valid JSON.
    demo = {
        "system": "a ride-hailing platform",
        "components": [
            {"name": "API Gateway", "responsibility": "route + auth client requests", "tech": "Envoy"},
            {"name": "Matching Service", "responsibility": "pair riders with drivers", "tech": "Go"},
            {"name": "Location Service", "responsibility": "ingest driver GPS", "tech": "Go + Redis geo"},
            {"name": "Trip Service", "responsibility": "trip lifecycle + pricing", "tech": "Java"},
        ],
        "connections": [
            {"from": "API Gateway", "to": "Matching Service", "label": "request ride"},
            {"from": "Matching Service", "to": "Location Service", "label": "nearby drivers"},
            {"from": "Matching Service", "to": "Trip Service", "label": "create trip"},
        ],
        "data_stores": [
            {"name": "trips-db", "kind": "PostgreSQL"},
            {"name": "driver-geo", "kind": "Redis"},
            {"name": "events", "kind": "Kafka"},
        ],
        "risks": ["hot-partition on dense city cells", "matching latency spikes at surge"],
    }

    from ormica.brain import MockBrain

    def reply(messages):
        text = messages[-1].content
        return json.dumps(demo) if "Output ONLY JSON" in text else "• (offline specialist note)"

    return MockBrain(reply_fn=reply), "MockBrain (offline)"


def design(system: str, brain) -> dict:
    """Run the colony and return the validated architecture spec (as a dict)."""
    org = Ormica("Ormica Architect")
    lead = org.spawn("lead-architect", role="architect")

    # 1. each specialist analyses its slice of the system (breadth)
    notes = []
    for name, brief in SPECIALISTS.items():
        node = org.spawn(name, under=lead, role="architect")
        agent = org.agent(node, brain=brain)   # fully wired — no manual events plumbing
        q = f"For the system: {system}\nSpecify {brief}. Reply in 3-5 concise bullet points."
        print(f"  · {name} analysing…", flush=True)
        notes.append(f"[{name}]\n{agent.act(q).content}")

    # 2. the lead synthesises a typed, grounded architecture (retries if malformed)
    con = Constitution([grounded(artifact_oracle(Architecture))])
    lead_agent = org.agent(lead, brain=brain, constitution=con)   # override the constitution
    print("  · lead synthesising the architecture…", flush=True)
    prompt = _SYNTH.format(system=system, notes="\n\n".join(notes))
    # a full architecture JSON is large — give it room so it isn't truncated
    resp = lead_agent.act(prompt, max_verify_attempts=3, max_tokens=8192)
    return Architecture.parse(resp.content).data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica architect demo")
    ap.add_argument("system", nargs="?", default="a ride-hailing platform at 10M users",
                    help="the system to design")
    ap.add_argument("--out", default="architecture.json", help="where to save the spec")
    args = ap.parse_args(argv)

    brain, label = pick_brain()
    print(f"brain: {label}\nsystem: {args.system}\n")
    spec = design(args.system, brain)

    print("\n=== ARCHITECTURE ===")
    print(f"system: {spec.get('system')}")
    print(f"components ({len(spec.get('components', []))}):")
    for c in spec.get("components", []):
        print(f"  • {c.get('name')} — {c.get('responsibility')}  [{c.get('tech')}]")
    print(f"connections: {len(spec.get('connections', []))}   "
          f"data stores: {len(spec.get('data_stores', []))}   "
          f"risks: {len(spec.get('risks', []))}")

    with open(args.out, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"\nsaved → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
