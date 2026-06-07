"""Agent — a Node coupled to a Brain, optionally wired to memory and signals."""
from __future__ import annotations

from typing import Any, Optional, Union

from .arbor import Node, NodeState
from .brain import (
    AsyncBrain,
    BudgetExhausted,
    Brain,
    Message,
    Prompt,
    Response,
    Tool,
    ToolCall,
    TokenBudget,
)
from .cortex import Constitution
from .mycelium import Mycelium
from .stigma import Signal, Stigma


class ToolLoopExceeded(RuntimeError):
    """Raised when ``act_with_tools`` hits ``max_iterations`` without a final answer."""


def _tools_by_name(tools: list[Tool]) -> dict[str, Tool]:
    return {t.name: t for t in tools}


def _run_tool(tool: Tool, call: ToolCall) -> Message:
    """Execute a tool call and wrap the result as a tool-role Message."""
    try:
        result = tool(**call.arguments)
    except Exception as exc:  # noqa: BLE001 — surface to the model
        return Message(
            role="tool",
            content=f"{type(exc).__name__}: {exc}",
            tool_call_id=call.id,
        )
    return Message(role="tool", content=str(result), tool_call_id=call.id)


class _AgentBase:
    """Common state and helpers shared by sync :class:`Agent` and :class:`AsyncAgent`."""

    def __init__(
        self,
        node: Node,
        brain: Union[Brain, AsyncBrain],
        *,
        memory: Optional[Mycelium] = None,
        signals: Optional[Stigma] = None,
        system_prompt: str = "",
        budget: Optional[TokenBudget] = None,
        constitution: Optional[Constitution] = None,
        sense_prefixes: tuple = (),
        top_n_sensed: int = 5,
    ) -> None:
        self.node = node
        self.brain = brain
        self.memory = memory
        self.signals = signals
        self.system_prompt = system_prompt
        self.budget = budget
        self.constitution = constitution
        # Stigma sensing — when set, _compose_system injects live trails
        # whose topic starts with any of these prefixes. Explicit kwarg
        # wins; otherwise falls back to node.meta["sense_prefixes"]
        # (stamped by colony templates that declare sense_prefixes:).
        # Empty tuple = sensing off, preserving v0.1 behavior.
        if not sense_prefixes:
            sense_prefixes = tuple(node.meta.get("sense_prefixes", ()))
        self.sense_prefixes: tuple = tuple(sense_prefixes)
        self.top_n_sensed: int = top_n_sensed
        # Observability — set by runners so think calls flow into a Trace.
        self.events: Any = None
        self.task_id: str = ""
        # Runtime Task object — set by runners so pre-stage rules can read
        # ctx["task"].priority / .target etc. ``None`` when an Agent is
        # driven directly (no runner), in which case rules should treat the
        # absence as "no runtime task in this context".
        self.runtime_task: Any = None

    def _record_think(
        self,
        messages: list,
        system: Optional[str],
        tools: list,
        response: Any,
    ) -> None:
        if self.events is None:
            return
        from .observe import emit_think_event

        emit_think_event(
            self.events,
            task_id=self.task_id,
            node_id=self.node.id,
            messages=messages,
            system=system,
            tools=tools,
            response=response,
        )

    def _merged_constitution(self, stage: str):
        """Compose the org Constitution with rules attached to ancestor Nodes.

        Per-node rules cascade down the tree: a rule attached to a Node
        applies to every think / spawn under that subtree. Rules attached
        to the root behave like an org-wide Constitution. Returns a fresh
        :class:`Constitution` carrying just the stage-relevant rules — or
        an empty one when nothing applies, which is the cheap-skip case.
        """
        from .cortex import Constitution

        rules = []
        if self.constitution is not None:
            rules.extend(self.constitution.for_stage(stage))
        for ancestor in self.node.path():
            rules.extend(r for r in ancestor.rules if r.stage == stage)
        return Constitution(rules)

    def _enforce_constitution(self, prompt: Any) -> None:
        """Raise :class:`RuleViolation` for hard rules; emit events for soft.

        Evaluates the org Constitution **plus** any rules attached to ancestor
        Nodes (``node.rules``) for ``stage="pre"``. Per-node rules cascade
        down the tree.
        """
        merged = self._merged_constitution("pre")
        if len(merged) == 0:
            return
        soft = merged.enforce(
            {
                "node": self.node,
                "role": self.node.role,
                "task_text": self.node.task,
                "task": self.runtime_task,
                "prompt": prompt,
                "budget": self.budget,
            },
            stage="pre",
        )
        self._emit_soft_violations(soft, stage="pre")

    def _enforce_constitution_post(self, prompt: Any, response: Any) -> None:
        """Raise :class:`RuleViolation` for hard post-stage rules; emit events for soft.

        Runs after a successful ``brain.think`` with the response available. For
        ``act_with_tools`` this fires only on the final (text) response, not on
        intermediate tool-use responses — the rule's view of "what the agent did"
        should be the user-visible answer. Composes the org Constitution with
        ancestor-attached rules the same way pre-stage does.
        """
        merged = self._merged_constitution("post")
        if len(merged) == 0:
            return
        soft = merged.enforce(
            {
                "node": self.node,
                "role": self.node.role,
                "task_text": self.node.task,
                "task": self.runtime_task,
                "prompt": prompt,
                "response": response,
                "budget": self.budget,
            },
            stage="post",
        )
        self._emit_soft_violations(soft, stage="post")

    def _emit_soft_violations(self, soft: list, *, stage: str) -> None:
        if self.events is None or not soft:
            return
        from .observe import RULE_SOFT_VIOLATION

        for v in soft:
            self.events.emit(
                RULE_SOFT_VIOLATION,
                source="constitution",
                rule=v.rule.name,
                reason=v.reason,
                node=self.node.name,
                task_id=self.task_id,
                stage=stage,
            )

    def _compose_system(self) -> Optional[str]:
        parts: list[str] = []
        # Colonies stamp a default system prompt onto node.meta when they
        # plant a template; the explicit Agent kwarg overrides it.
        explicit = self.system_prompt or self.node.meta.get("system_prompt", "")
        if explicit:
            parts.append(explicit)
        if self.node.role:
            parts.append(f"Your role: {self.node.role}.")
        if self.node.task:
            parts.append(f"Your task: {self.node.task}")
        sensed = self._sensed_block()
        if sensed:
            parts.append(sensed)
        return "\n\n".join(parts) if parts else None

    def _sensed_block(self) -> Optional[str]:
        """Render the top matching stigma trails as a system-prompt block.

        Returns ``None`` when sensing is off (no prefixes or no Stigma)
        or when no live trails match. The block lists trails strongest
        first; the agent sees what the colony is currently doing without
        having to query memory itself.
        """
        if self.signals is None or not self.sense_prefixes:
            return None
        relevant = [
            s for s in self.signals.trails()
            if any(s.topic.startswith(p) for p in self.sense_prefixes)
        ][: self.top_n_sensed]
        if not relevant:
            return None
        lines = "\n".join(
            f"  - {s.topic} (strength {s.strength:.2f})" for s in relevant
        )
        return f"Active colony signals (strongest first):\n{lines}"

    def _check_budget(self) -> None:
        if self.budget is not None and self.budget.exhausted:
            raise BudgetExhausted(
                f"agent {self.node.name!r} has no tokens left "
                f"({self.budget.used}/{self.budget.limit})"
            )

    # --- memory shortcuts (no-ops without a mycelium) ---

    def remember(self, key: str, value: Any, **kw: Any) -> None:
        if self.memory is not None:
            self.memory.write(key, value, author=self.node.id, **kw)

    def recall(self, key: str, default: Any = None) -> Any:
        if self.memory is None:
            return default
        return self.memory.get(key, default=default)

    # --- signal shortcuts (no-ops without a stigma) ---

    def emit(self, topic: str, *, strength: float = 1.0) -> None:
        if self.signals is not None:
            self.signals.emit(topic, strength=strength, by=self.node.id)

    def reinforce(self, topic: str, *, amount: float = 1.0) -> None:
        if self.signals is not None:
            self.signals.reinforce(topic, amount=amount, by=self.node.id)

    def sense(self, topic: str) -> Optional[Signal]:
        return self.signals.sense(topic) if self.signals is not None else None


class Agent(_AgentBase):
    """A thinking entity in the colony — sync.

    Wraps a :class:`Node` and a :class:`Brain`, with optional shared
    :class:`Mycelium` (memory) and :class:`Stigma` (signals). ``act()``
    is one think turn; the node's state moves IDLE → WORKING → DONE
    (or FAILED on exception).
    """

    brain: Brain  # type: ignore[assignment]

    def act(self, prompt: Prompt, *, max_tokens: int = 1024) -> Response:
        self._check_budget()
        self._enforce_constitution(prompt)
        system = self._compose_system()
        self.node.state = NodeState.WORKING
        messages = _initial_messages(prompt)
        try:
            response = self.brain.think(prompt, system=system, max_tokens=max_tokens)
        except Exception:
            self.node.state = NodeState.FAILED
            raise

        self._record_think(messages, system, [], response)
        if self.budget is not None:
            self.budget.consume(response.tokens_used)
        try:
            self._enforce_constitution_post(prompt, response)
        except Exception:
            self.node.state = NodeState.FAILED
            raise
        self.node.state = NodeState.DONE
        return response

    def act_with_tools(
        self,
        prompt: Prompt,
        tools: list[Tool],
        *,
        max_tokens: int = 1024,
        max_iterations: int = 8,
    ) -> Response:
        """Multi-turn loop: think → tool_use → execute → think → ... until done.

        Returns the final :class:`Response` (without ``tool_calls``).
        Raises :class:`ToolLoopExceeded` if the model keeps requesting tools
        past ``max_iterations``.
        """
        self._check_budget()
        system = self._compose_system()
        registry = _tools_by_name(tools)
        history: list[Message] = list(_initial_messages(prompt))
        self.node.state = NodeState.WORKING

        try:
            for _ in range(max_iterations):
                response = self.brain.think(
                    history, system=system, max_tokens=max_tokens, tools=tools
                )
                self._record_think(list(history), system, tools, response)
                if self.budget is not None:
                    self.budget.consume(response.tokens_used)
                if not response.wants_tools:
                    self._enforce_constitution_post(prompt, response)
                    self.node.state = NodeState.DONE
                    return response

                # Record the assistant turn that asked for tools.
                history.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=tuple(response.tool_calls),
                    )
                )
                # Execute each call and append a tool-role result.
                for call in response.tool_calls:
                    tool = registry.get(call.name)
                    if tool is None:
                        history.append(
                            Message(
                                role="tool",
                                content=f"unknown tool: {call.name!r}",
                                tool_call_id=call.id,
                            )
                        )
                        continue
                    history.append(_run_tool(tool, call))
        except Exception:
            self.node.state = NodeState.FAILED
            raise

        self.node.state = NodeState.FAILED
        raise ToolLoopExceeded(
            f"agent {self.node.name!r} still asking for tools after "
            f"{max_iterations} iterations"
        )


def _initial_messages(prompt: Prompt) -> list[Message]:
    if isinstance(prompt, str):
        return [Message(role="user", content=prompt)]
    return list(prompt)


class AsyncAgent(_AgentBase):
    """Async sibling of :class:`Agent` — wraps an :class:`AsyncBrain`.

    Identical surface to :class:`Agent` except :meth:`act` is awaitable.
    Used by :class:`AsyncTaskRunner` for concurrent task execution.
    """

    brain: AsyncBrain  # type: ignore[assignment]

    async def act(self, prompt: Prompt, *, max_tokens: int = 1024) -> Response:
        self._check_budget()
        self._enforce_constitution(prompt)
        system = self._compose_system()
        self.node.state = NodeState.WORKING
        messages = _initial_messages(prompt)
        try:
            response = await self.brain.think(
                prompt, system=system, max_tokens=max_tokens
            )
        except Exception:
            self.node.state = NodeState.FAILED
            raise

        self._record_think(messages, system, [], response)
        if self.budget is not None:
            self.budget.consume(response.tokens_used)
        try:
            self._enforce_constitution_post(prompt, response)
        except Exception:
            self.node.state = NodeState.FAILED
            raise
        self.node.state = NodeState.DONE
        return response

    async def act_with_tools(
        self,
        prompt: Prompt,
        tools: list[Tool],
        *,
        max_tokens: int = 1024,
        max_iterations: int = 8,
    ) -> Response:
        """Async multi-turn tool loop. See :meth:`Agent.act_with_tools`."""
        self._check_budget()
        system = self._compose_system()
        registry = _tools_by_name(tools)
        history: list[Message] = list(_initial_messages(prompt))
        self.node.state = NodeState.WORKING

        try:
            for _ in range(max_iterations):
                response = await self.brain.think(
                    history, system=system, max_tokens=max_tokens, tools=tools
                )
                self._record_think(list(history), system, tools, response)
                if self.budget is not None:
                    self.budget.consume(response.tokens_used)
                if not response.wants_tools:
                    self._enforce_constitution_post(prompt, response)
                    self.node.state = NodeState.DONE
                    return response

                history.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=tuple(response.tool_calls),
                    )
                )
                for call in response.tool_calls:
                    tool = registry.get(call.name)
                    if tool is None:
                        history.append(
                            Message(
                                role="tool",
                                content=f"unknown tool: {call.name!r}",
                                tool_call_id=call.id,
                            )
                        )
                        continue
                    history.append(_run_tool(tool, call))
        except Exception:
            self.node.state = NodeState.FAILED
            raise

        self.node.state = NodeState.FAILED
        raise ToolLoopExceeded(
            f"agent {self.node.name!r} still asking for tools after "
            f"{max_iterations} iterations"
        )
