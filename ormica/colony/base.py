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
