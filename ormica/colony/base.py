"""AgentTemplate and Colony — the declarative layer that industries plug into."""
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Optional

from ormica.arbor import Node

if TYPE_CHECKING:
    from ormica.core import Ormica


class AgentTemplate:
    """A reusable description of an agent — role, default task, system prompt.

    Subclass and set the class attributes. ``plant(org)`` spawns a node
    in the org's tree from the template and stamps the system prompt
    onto ``node.meta``. The runtime :class:`Agent` reads that meta as
    a fallback when no explicit ``system_prompt`` is passed.

    Templates are declarative — they do not invoke a Brain. The runtime
    Agent does that.
    """

    name: ClassVar[str] = ""
    role: ClassVar[str] = ""
    task: ClassVar[str] = ""
    system_prompt: ClassVar[str] = ""
    # Per-template Constitution rules, copied onto ``node.rules`` at plant
    # time. Tuple by default so the empty class-level value is shared safely;
    # YAML-loaded templates supply a tuple of already-built Rule objects.
    rules: ClassVar = ()
    # Stigma topic prefixes this template's agent reads into its system
    # prompt at think time. Empty tuple = no sensing (back-compat).
    sense_prefixes: ClassVar[tuple] = ()
    # Static stigma emits: each entry is (topic, strength) — reinforced
    # on every task finalize regardless of LLM behavior. Lets a colony
    # author declare a domain-meaningful topic vocabulary without writing
    # a custom Agent. Empty tuple = no static emits (back-compat).
    emits: ClassVar[tuple] = ()
    # LLM-facing emit_signal tool config (Option D). When set, the
    # runtime switches this node's agent from ``act`` to ``act_with_tools``
    # and gives the LLM a typed ``emit_signal(topic, strength)`` tool
    # bound to the declared vocabulary. ``None`` = no tool (back-compat).
    emit_tool_config: ClassVar = None

    @classmethod
    def plant(
        cls,
        org: "Ormica",
        *,
        under: Optional[Node] = None,
        name: Optional[str] = None,
        task: Optional[str] = None,
    ) -> Node:
        node = org.tree.spawn(
            under if under is not None else org.root,
            name or cls.name or cls.role or cls.__name__.lower(),
            role=cls.role,
            task=task if task is not None else cls.task,
        )
        if cls.system_prompt:
            node.meta["system_prompt"] = cls.system_prompt
        if cls.rules:
            node.rules.extend(cls.rules)
        if cls.sense_prefixes:
            node.meta["sense_prefixes"] = list(cls.sense_prefixes)
        if cls.emits:
            # Store as list-of-lists for JSON / yaml round-trip cleanliness.
            node.meta["emits"] = [list(pair) for pair in cls.emits]
        if cls.emit_tool_config is not None:
            # Stash the EmitToolConfig dataclass; runtime reads + builds the
            # Tool per-task (per-task state, per-task rate-limit reset).
            node.meta["emit_tool_config"] = cls.emit_tool_config
        node.meta["template"] = cls.__name__
        return node


class Colony:
    """A collection of AgentTemplates describing an industry's department layout.

    Subclass, set ``name``, and override :meth:`templates`. Calling
    ``colony.plant(org)`` spawns one node per template under the org's
    root (or a chosen sub-node).

    For hierarchical structures, override :meth:`plant` directly.
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def templates(self) -> list[type[AgentTemplate]]:
        return []

    def plant(self, org: "Ormica", *, under: Optional[Node] = None) -> list[Node]:
        parent = under if under is not None else org.root
        return [t.plant(org, under=parent) for t in self.templates()]
