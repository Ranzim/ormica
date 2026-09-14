"""Postbox — direct, addressed messaging between agents.

.. note:: **Opt-in — not the default coordination model.** Ormica's core
   philosophy is *stigmergic* coordination: agents post to a shared pheromone
   field (``stigma`` + ``mycelium``) and coordination emerges, rather than
   relying on direct message-passing. The postbox deliberately provides the
   *other* model for the narrow cases where emergence isn't enough — a tight,
   specific handoff ("Agent A, I need exactly this before I continue"). Reach
   for signals + shared memory first; use the postbox only when a direct,
   addressed request is genuinely required. It is off unless you wire it in.

Stigmergy (``stigma``) is *indirect* coordination: an agent drops a signal and
whoever cares senses it. The postbox is the direct alternative — addressed
messages with replies and threads.

Like :class:`~ormica.stigma.Stigma`, it's a thin layer over
:class:`~ormica.mycelium.Mycelium` — messages live under the ``mailbox/``
key prefix, so they persist and share the same backend as everything else. A
message is addressed to a node id and lands in that node's inbox until read.

    box = Postbox(org.memory)
    box.send(sender=a.id, recipient=b.id, body="Need the pricing table", subject="pricing")
    for msg in box.unread(b.id):
        reply = box.reply(msg, "Here it is: ...")

Agents get shortcuts (:meth:`Agent.send`, :meth:`Agent.inbox`, …) and the org
facade resolves department names to node ids.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Union
from uuid import uuid4

from ormica.arbor import Node
from ormica.brain import Tool
from ormica.mycelium import Entry, Mycelium

NodeRef = Union[Node, str]


def _new_id() -> str:
    return uuid4().hex[:12]


def _node_id(ref: NodeRef) -> str:
    return ref.id if isinstance(ref, Node) else str(ref)


@dataclass
class Message:
    """One directed message from ``sender`` to ``recipient`` (both node ids)."""

    sender: str
    recipient: str
    body: str
    subject: str = ""
    id: str = field(default_factory=_new_id)
    in_reply_to: Optional[str] = None
    created_at: float = 0.0
    read: bool = False
    meta: dict = field(default_factory=dict)

    def to_value(self) -> dict:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "body": self.body,
            "subject": self.subject,
            "id": self.id,
            "in_reply_to": self.in_reply_to,
            "created_at": self.created_at,
            "read": self.read,
            "meta": self.meta,
        }

    @classmethod
    def from_value(cls, value: dict) -> "Message":
        return cls(
            sender=value["sender"],
            recipient=value["recipient"],
            body=value["body"],
            subject=value.get("subject", ""),
            id=value["id"],
            in_reply_to=value.get("in_reply_to"),
            created_at=value.get("created_at", 0.0),
            read=value.get("read", False),
            meta=value.get("meta") or {},
        )


class Postbox:
    """Addressed messaging between nodes, stored in a :class:`Mycelium`."""

    KEY_PREFIX = "mailbox/"

    def __init__(self, mycelium: Mycelium) -> None:
        self.mycelium = mycelium

    # --- keys ---

    def _key(self, recipient: str, message_id: str) -> str:
        return f"{self.KEY_PREFIX}{recipient}/{message_id}"

    def _inbox_prefix(self, recipient: str) -> str:
        return f"{self.KEY_PREFIX}{recipient}/"

    # --- writes ---

    def send(
        self,
        sender: NodeRef,
        recipient: NodeRef,
        body: str,
        *,
        subject: str = "",
        in_reply_to: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> Message:
        """Deliver a message to ``recipient``'s inbox. Returns the Message."""
        msg = Message(
            sender=_node_id(sender),
            recipient=_node_id(recipient),
            body=body,
            subject=subject,
            in_reply_to=in_reply_to,
            created_at=self.mycelium.now(),
            meta=dict(meta) if meta else {},
        )
        self.mycelium.write(
            self._key(msg.recipient, msg.id),
            value=msg.to_value(),
            author=msg.sender,
            meta={"kind": "postbox.message", "recipient": msg.recipient},
        )
        return msg

    def reply(
        self,
        message: Message,
        body: str,
        *,
        subject: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> Message:
        """Reply to ``message`` — swaps sender/recipient, links ``in_reply_to``."""
        subj = subject if subject is not None else _re_subject(message.subject)
        return self.send(
            sender=message.recipient,
            recipient=message.sender,
            body=body,
            subject=subj,
            in_reply_to=message.id,
            meta=meta,
        )

    def mark_read(self, message: Message) -> None:
        """Flag ``message`` as read (idempotent)."""
        message.read = True
        entry = self.mycelium.read(self._key(message.recipient, message.id))
        if entry is None:
            return
        self.mycelium.write(
            self._key(message.recipient, message.id),
            value=message.to_value(),
            author=message.sender,
            meta=dict(entry.meta),
        )

    # --- reads ---

    def inbox(self, recipient: NodeRef, *, unread_only: bool = False) -> list[Message]:
        """Messages addressed to ``recipient``, oldest first."""
        rid = _node_id(recipient)
        prefix = self._inbox_prefix(rid)
        msgs = [
            Message.from_value(e.value)
            for e in self.mycelium.all()
            if e.key.startswith(prefix)
        ]
        if unread_only:
            msgs = [m for m in msgs if not m.read]
        msgs.sort(key=lambda m: m.created_at)
        return msgs

    def unread(self, recipient: NodeRef) -> list[Message]:
        return self.inbox(recipient, unread_only=True)

    def fetch(self, recipient: NodeRef) -> list[Message]:
        """Return unread messages **and mark them read** (an inbox drain)."""
        msgs = self.unread(recipient)
        for m in msgs:
            self.mark_read(m)
        return msgs

    def thread(self, message: Message) -> list[Message]:
        """The whole conversation ``message`` belongs to, oldest first.

        Follows ``in_reply_to`` links in both directions across mailboxes, so a
        back-and-forth between two agents comes back as one ordered list.
        """
        everything = {
            m.id: m
            for e in self.mycelium.all()
            if e.key.startswith(self.KEY_PREFIX)
            for m in [Message.from_value(e.value)]
        }
        # Build an undirected link graph over message ids and walk the component.
        seen: set[str] = set()
        stack = [message.id]
        while stack:
            mid = stack.pop()
            if mid in seen or mid not in everything:
                continue
            seen.add(mid)
            cur = everything[mid]
            if cur.in_reply_to:
                stack.append(cur.in_reply_to)
            stack.extend(
                m.id for m in everything.values() if m.in_reply_to == mid
            )
        chain = [everything[mid] for mid in seen]
        chain.sort(key=lambda m: m.created_at)
        return chain


def _re_subject(subject: str) -> str:
    if not subject:
        return ""
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def _from_entry(entry: Entry) -> Message:  # convenience for callers scanning memory
    return Message.from_value(entry.value)


# --- LLM-facing send_message tool ---------------------------------------------
#
# The direct-messaging counterpart to stigma's emit_signal tool: lets an agent
# message peers *autonomously* mid-turn. Same production constraints — a bounded
# recipient vocabulary declared as a schema enum, a per-turn rate limit, and
# refusals returned as strings (never raised) so the model can adjust.


@dataclass(frozen=True)
class MessageToolConfig:
    """Declarative config for the LLM-facing ``send_message`` tool.

    ``recipients`` is the bounded set of identifiers the agent may message —
    department names or node ids, resolved to ids by the builder's ``resolve``
    hook. Listed in the tool schema's ``enum`` so a sensible model cannot
    invent recipients; one that ignores the schema gets a refusal back.
    """

    recipients: tuple[str, ...]
    max_per_turn: int = 3
    max_body_chars: int = 2000

    def __post_init__(self) -> None:
        if not self.recipients:
            raise ValueError("MessageToolConfig.recipients must be non-empty")
        if any(not isinstance(r, str) or not r for r in self.recipients):
            raise ValueError(
                "MessageToolConfig.recipients entries must be non-empty strings"
            )
        if self.max_per_turn < 1:
            raise ValueError(
                f"MessageToolConfig.max_per_turn must be >= 1, got {self.max_per_turn}"
            )
        if self.max_body_chars < 1:
            raise ValueError(
                f"MessageToolConfig.max_body_chars must be >= 1, "
                f"got {self.max_body_chars}"
            )


class MessageToolBuilder:
    """Constructs a per-turn-stateful ``send_message`` Tool for one agent.

    Per-agent-per-task, like :class:`~ormica.stigma.EmitToolBuilder`: it owns
    the rate counter. ``resolve`` maps a vocabulary entry (e.g. a department
    name) to a recipient node id; the default treats entries as ids already.
    """

    def __init__(
        self,
        postbox: Postbox,
        node: Node,
        config: MessageToolConfig,
        *,
        resolve: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.postbox = postbox
        self.node = node
        self.config = config
        self.resolve = resolve or (lambda x: x)
        self.sent_this_turn: int = 0
        self.refusals: list[str] = []

    def reset(self) -> None:
        """Zero the per-turn counter. Runtime calls this before each task."""
        self.sent_this_turn = 0
        self.refusals = []

    def _refuse(self, msg: str, *, count: bool) -> str:
        self.refusals.append(msg)
        if count:
            self.sent_this_turn += 1
        return msg

    def __call__(self, recipient: str, body: str, subject: str = "") -> str:
        """The tool body. Returns a string the LLM reads as the result."""
        # Rate limit first, so a flood of malformed calls still counts.
        if self.sent_this_turn >= self.config.max_per_turn:
            return self._refuse(
                f"refused: rate limit — already sent "
                f"{self.config.max_per_turn} message(s) this turn",
                count=False,
            )
        if recipient not in self.config.recipients:
            return self._refuse(
                f"refused: unknown recipient {recipient!r}. "
                f"Allowed: {list(self.config.recipients)}",
                count=True,
            )
        if not body or not body.strip():
            return self._refuse("refused: message body is empty", count=True)
        if len(body) > self.config.max_body_chars:
            return self._refuse(
                f"refused: body too long ({len(body)} chars, "
                f"max {self.config.max_body_chars})",
                count=True,
            )
        try:
            rid = self.resolve(recipient)
        except Exception as exc:
            return self._refuse(
                f"refused: could not resolve recipient {recipient!r}: "
                f"{type(exc).__name__}: {exc}",
                count=True,
            )
        try:
            msg = self.postbox.send(
                self.node.id, rid, body, subject=subject
            )
        except Exception as exc:
            return self._refuse(
                f"refused: send failed: {type(exc).__name__}: {exc}", count=True
            )
        self.sent_this_turn += 1
        return f"ok: message sent to {recipient!r} (id {msg.id})"

    def as_tool(self) -> Tool:
        """Materialize the configured send function as a Tool the LLM sees."""
        recipients = list(self.config.recipients)
        description = (
            "Send a direct message to another agent in the colony. Use this "
            "when you need a specific result or action from a particular peer "
            "before you can continue — not for broadcasts. "
            f"Allowed recipients: {recipients}. "
            f"You may call this at most {self.config.max_per_turn} time(s) per turn."
        )
        schema = {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "enum": recipients,
                    "description": (
                        "Who to message. Must be one of the allowed recipients."
                    ),
                },
                "body": {
                    "type": "string",
                    "maxLength": self.config.max_body_chars,
                    "description": "The message text.",
                },
                "subject": {
                    "type": "string",
                    "description": "Optional short subject line.",
                },
            },
            "required": ["recipient", "body"],
        }
        return Tool(
            name="send_message",
            description=description,
            fn=self,
            schema=schema,
        )
