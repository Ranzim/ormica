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
from .cortex import Constitution, VerificationFailed
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
        auto_recall: int = 0,
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
        # Auto-RAG — when > 0, before each think the agent searches shared
        # memory with the prompt and injects the top-k relevant entries into
        # its system prompt. 0 = off (default). Falls back to node.meta.
        self.auto_recall: int = auto_recall or int(node.meta.get("auto_recall", 0))
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

    # --- verify stage (check-and-retry) ---

    def _has_verify_rules(self) -> bool:
        return len(self._merged_constitution("verify")) > 0

    def _verify_check(self, prompt: Any, response: Any, attempt: int):
        """Run verify-stage rules. Returns ``(hard, soft)`` violation lists."""
        merged = self._merged_constitution("verify")
        violations = merged.check(
            {
                "node": self.node,
                "role": self.node.role,
                "task_text": self.node.task,
                "task": self.runtime_task,
                "prompt": prompt,
                "response": response,
                "attempt": attempt,
                "budget": self.budget,
            },
            stage="verify",
        )
        hard = [v for v in violations if v.rule.severity == "hard"]
        soft = [v for v in violations if v.rule.severity == "soft"]
        return hard, soft

    def _verify_feedback_prompt(self, prompt: Any, response: Any, violations: list):
        """Build the retry prompt: original + failed answer + correction note.

        The note carries each failed rule's human-readable description (and the
        raw reason) so the model knows what to fix, not just that it failed.
        """
        messages = list(_initial_messages(prompt))
        messages.append(Message(role="assistant", content=response.content))
        messages.append(self._verify_feedback_message(violations))
        return messages

    def _verify_feedback_message(self, violations: list) -> "Message":
        """A single user-turn correction note, for appending to a tool-loop history."""
        reasons = "; ".join(
            f"{v.rule.description or v.rule.name} ({v.reason})" for v in violations
        )
        return Message(
            role="user",
            content=(
                "Your previous answer failed verification: "
                f"{reasons}. Correct the issue and answer again."
            ),
        )

    def _passed_verify(
        self, prompt: Any, response: Any, history: list, attempt: int, max_attempts: int
    ) -> bool:
        """Verify the tool loop's final response. Returns True if accepted.

        On a hard failure with attempts left, appends the answer + a correction
        note to ``history`` and returns False (the caller loops so the model can
        revise — it may call tools again). Exhausting attempts raises
        :class:`VerificationFailed`.
        """
        hard, soft = self._verify_check(prompt, response, attempt)
        self._emit_soft_violations(soft, stage="verify")
        if not hard:
            return True
        if attempt < max_attempts:
            self._emit_verify_retry(hard, attempt)
            history.append(Message(role="assistant", content=response.content))
            history.append(self._verify_feedback_message(hard))
            return False
        self._emit_verify_failed(hard, attempt)
        raise VerificationFailed(hard, attempts=attempt)

    def _emit_verify_retry(self, violations: list, attempt: int) -> None:
        if self.events is None:
            return
        from .observe import VERIFY_RETRY

        self.events.emit(
            VERIFY_RETRY,
            source="verify",
            node=self.node.name,
            task_id=self.task_id,
            attempt=attempt,
            rules=[v.rule.name for v in violations],
            reasons=[v.reason for v in violations],
        )

    def _emit_verify_failed(self, violations: list, attempts: int) -> None:
        if self.events is None:
            return
        from .observe import VERIFY_FAILED

        self.events.emit(
            VERIFY_FAILED,
            source="verify",
            node=self.node.name,
            task_id=self.task_id,
            attempts=attempts,
            rules=[v.rule.name for v in violations],
            reasons=[v.reason for v in violations],
        )

    def _compose_system(self, prompt: Any = None) -> Optional[str]:
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
        recalled = self._recalled_block(prompt)
        if recalled:
            parts.append(recalled)
        return "\n\n".join(parts) if parts else None

    def _recalled_block(self, prompt: Any) -> Optional[str]:
        """Auto-RAG: inject the top-k memory entries most relevant to ``prompt``.

        Returns ``None`` when auto-recall is off, there's no searchable memory,
        or nothing relevant is found. Internal keys (signals / mailbox / task /
        trace records) are excluded — only actual knowledge is surfaced.
        """
        if self.auto_recall < 1 or self.memory is None or prompt is None:
            return None
        from ormica.mycelium import SearchableBackend

        if not isinstance(self.memory.backend, SearchableBackend):
            return None
        query = (
            prompt if isinstance(prompt, str)
            else " ".join(getattr(m, "content", "") or "" for m in prompt).strip()
        )
        if not query:
            return None
        try:
            matches = self.memory.search(query, k=self.auto_recall)
        except Exception:  # noqa: BLE001 — recall is best-effort, never fatal
            return None
        internal = ("stigma/", "mailbox/", "tasks/", "traces/")
        hits = [
            m for m in matches
            if not any(m.entry.key.startswith(p) for p in internal)
        ]
        if not hits:
            return None
        lines = "\n".join(
            f"  - {m.entry.key}: {str(m.entry.value)[:200]}" for m in hits
        )
        return f"Relevant knowledge from the colony's memory:\n{lines}"

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
            self._emit_memory("memory.write", key=key)

    def recall(self, key: str, default: Any = None) -> Any:
        if self.memory is None:
            return default
        value = self.memory.get(key, default=default)
        self._emit_memory("memory.read", key=key, hit=value is not default)
        return value

    def recall_relevant(self, query: str, k: int = 5) -> list:
        """Relevance-recall: the ``k`` entries most related to ``query``.

        Returns a list of :class:`~ormica.mycelium.Match` (empty without a
        mycelium). Requires a searchable backend — see
        :class:`~ormica.mycelium.InMemorySemanticBackend`.
        """
        if self.memory is None:
            return []
        matches = self.memory.search(query, k=k)
        self._emit_memory("memory.read", query=query, k=k, hits=len(matches))
        return matches

    def _emit_memory(self, event_type: str, **payload: Any) -> None:
        """Emit a knowledge read/write event (no-op without an event bus).

        Fires at the agent level — this is *knowledge*, tagged with the node and
        task — not the internal signal/mailbox/trace writes on raw mycelium.
        """
        if self.events is None:
            return
        self.events.emit(
            event_type,
            source="memory",
            node=self.node.id,
            task_id=self.task_id,
            **payload,
        )

    # --- signal shortcuts (no-ops without a stigma) ---

    def emit(self, topic: str, *, strength: float = 1.0) -> None:
        if self.signals is not None:
            self.signals.emit(topic, strength=strength, by=self.node.id)

    def reinforce(self, topic: str, *, amount: float = 1.0) -> None:
        if self.signals is not None:
            self.signals.reinforce(topic, amount=amount, by=self.node.id)

    def sense(self, topic: str) -> Optional[Signal]:
        return self.signals.sense(topic) if self.signals is not None else None

    # --- direct messaging (no-ops without a mycelium) ---

    def _postbox(self):
        if self.memory is None:
            return None
        from .postbox import Postbox

        return Postbox(self.memory)

    def send(self, to: Any, body: str, *, subject: str = "", in_reply_to: Optional[str] = None):
        """Send a direct message to another node (a Node or node id)."""
        box = self._postbox()
        if box is None:
            return None
        msg = box.send(
            self.node.id, to, body, subject=subject, in_reply_to=in_reply_to
        )
        if self.events is not None:
            from .observe import MESSAGE_SENT

            self.events.emit(
                MESSAGE_SENT,
                source="postbox",
                sender=self.node.id,
                recipient=msg.recipient,
                subject=subject,
                task_id=self.task_id,
                message_id=msg.id,
            )
        return msg

    def reply(self, message: Any, body: str, *, subject: Optional[str] = None):
        """Reply to a received :class:`~ormica.postbox.Message`."""
        box = self._postbox()
        return None if box is None else box.reply(message, body, subject=subject)

    def inbox(self, *, unread_only: bool = False) -> list:
        box = self._postbox()
        return [] if box is None else box.inbox(self.node.id, unread_only=unread_only)

    def unread(self) -> list:
        box = self._postbox()
        return [] if box is None else box.unread(self.node.id)

    def fetch_messages(self) -> list:
        """Return unread messages and mark them read (drain the inbox)."""
        box = self._postbox()
        return [] if box is None else box.fetch(self.node.id)


class Agent(_AgentBase):
    """A thinking entity in the colony — sync.

    Wraps a :class:`Node` and a :class:`Brain`, with optional shared
    :class:`Mycelium` (memory) and :class:`Stigma` (signals). ``act()``
    is one think turn; the node's state moves IDLE → WORKING → DONE
    (or FAILED on exception).
    """

    brain: Brain  # type: ignore[assignment]

    def act(
        self,
        prompt: Prompt,
        *,
        max_tokens: int = 1024,
        max_verify_attempts: int = 3,
    ) -> Response:
        if max_verify_attempts < 1:
            raise ValueError("max_verify_attempts must be >= 1")
        self._enforce_constitution(prompt)
        system = self._compose_system(prompt)
        self.node.state = NodeState.WORKING
        has_verify = self._has_verify_rules()
        attempt_prompt: Prompt = prompt
        try:
            for attempt in range(1, max_verify_attempts + 1):
                self._check_budget()
                messages = _initial_messages(attempt_prompt)
                response = self.brain.think(
                    attempt_prompt, system=system, max_tokens=max_tokens
                )
                self._record_think(messages, system, [], response)
                if self.budget is not None:
                    self.budget.consume(response.tokens_used)
                self._enforce_constitution_post(prompt, response)
                if not has_verify:
                    break
                hard, soft = self._verify_check(prompt, response, attempt)
                self._emit_soft_violations(soft, stage="verify")
                if not hard:
                    break
                if attempt < max_verify_attempts:
                    self._emit_verify_retry(hard, attempt)
                    attempt_prompt = self._verify_feedback_prompt(
                        prompt, response, hard
                    )
                else:
                    self._emit_verify_failed(hard, attempt)
                    raise VerificationFailed(hard, attempts=attempt)
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
        max_verify_attempts: int = 3,
    ) -> Response:
        """Multi-turn loop: think → tool_use → execute → think → ... until done.

        Returns the final :class:`Response` (without ``tool_calls``). The final
        text response also passes the ``verify`` stage: a failed grounding check
        feeds the reason back and lets the model revise (it may call tools again),
        up to ``max_verify_attempts``, then raises :class:`VerificationFailed`.
        Raises :class:`ToolLoopExceeded` if the model keeps requesting tools
        past ``max_iterations``.
        """
        self._check_budget()
        system = self._compose_system(prompt)
        registry = _tools_by_name(tools)
        history: list[Message] = list(_initial_messages(prompt))
        self.node.state = NodeState.WORKING
        has_verify = self._has_verify_rules()
        verify_attempt = 1

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
                    if has_verify and not self._passed_verify(
                        prompt, response, history, verify_attempt, max_verify_attempts
                    ):
                        verify_attempt += 1
                        continue  # feedback appended to history; let the model revise
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

    async def act(
        self,
        prompt: Prompt,
        *,
        max_tokens: int = 1024,
        max_verify_attempts: int = 3,
    ) -> Response:
        if max_verify_attempts < 1:
            raise ValueError("max_verify_attempts must be >= 1")
        self._enforce_constitution(prompt)
        system = self._compose_system(prompt)
        self.node.state = NodeState.WORKING
        has_verify = self._has_verify_rules()
        attempt_prompt: Prompt = prompt
        try:
            for attempt in range(1, max_verify_attempts + 1):
                self._check_budget()
                messages = _initial_messages(attempt_prompt)
                response = await self.brain.think(
                    attempt_prompt, system=system, max_tokens=max_tokens
                )
                self._record_think(messages, system, [], response)
                if self.budget is not None:
                    self.budget.consume(response.tokens_used)
                self._enforce_constitution_post(prompt, response)
                if not has_verify:
                    break
                hard, soft = self._verify_check(prompt, response, attempt)
                self._emit_soft_violations(soft, stage="verify")
                if not hard:
                    break
                if attempt < max_verify_attempts:
                    self._emit_verify_retry(hard, attempt)
                    attempt_prompt = self._verify_feedback_prompt(
                        prompt, response, hard
                    )
                else:
                    self._emit_verify_failed(hard, attempt)
                    raise VerificationFailed(hard, attempts=attempt)
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
        max_verify_attempts: int = 3,
    ) -> Response:
        """Async multi-turn tool loop. See :meth:`Agent.act_with_tools`."""
        self._check_budget()
        system = self._compose_system(prompt)
        registry = _tools_by_name(tools)
        history: list[Message] = list(_initial_messages(prompt))
        self.node.state = NodeState.WORKING
        has_verify = self._has_verify_rules()
        verify_attempt = 1

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
                    if has_verify and not self._passed_verify(
                        prompt, response, history, verify_attempt, max_verify_attempts
                    ):
                        verify_attempt += 1
                        continue
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
