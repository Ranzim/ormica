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
    ) -> None:
        self.node = node
        self.brain = brain
        self.memory = memory
        self.signals = signals
        self.system_prompt = system_prompt
        self.budget = budget
        self.constitution = constitution
        # Observability — set by runners so think calls flow into a Trace.
        self.events: Any = None
        self.task_id: str = ""

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

    def _enforce_constitution(self, prompt: Any) -> None:
        """Raise :class:`RuleViolation` for hard rules; emit events for soft."""
        if self.constitution is None:
            return
        soft = self.constitution.enforce(
            {
                "node": self.node,
                "role": self.node.role,
                "task": self.node.task,
                "prompt": prompt,
                "budget": self.budget,
            },
            stage="pre",
        )
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
                stage="pre",
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
        return "\n\n".join(parts) if parts else None

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
        self.node.state = NodeState.DONE
        if self.budget is not None:
            self.budget.consume(response.tokens_used)
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
        self.node.state = NodeState.DONE
        if self.budget is not None:
            self.budget.consume(response.tokens_used)
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
