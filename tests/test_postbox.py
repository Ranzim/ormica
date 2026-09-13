"""Tests for direct agent-to-agent messaging (Postbox)."""
from ormica import Message, Ormica, Postbox
from ormica.agent import Agent
from ormica.arbor import Tree
from ormica.brain import MockBrain
from ormica.mycelium import InMemoryBackend, Mycelium
from ormica.observe import MESSAGE_SENT, CollectObserver, EventBus


def _mem() -> Mycelium:
    return Mycelium(InMemoryBackend())


# --- Postbox core -------------------------------------------------------------


def test_send_and_inbox():
    box = Postbox(_mem())
    box.send("alice", "bob", "hello bob", subject="hi")
    inbox = box.inbox("bob")
    assert len(inbox) == 1
    assert isinstance(inbox[0], Message)
    assert inbox[0].sender == "alice"
    assert inbox[0].body == "hello bob"
    assert box.inbox("alice") == []  # not addressed to alice


def test_unread_and_fetch_marks_read():
    box = Postbox(_mem())
    box.send("a", "b", "one")
    box.send("a", "b", "two")
    assert len(box.unread("b")) == 2
    drained = box.fetch("b")
    assert len(drained) == 2
    assert box.unread("b") == []  # fetch marked them read
    assert len(box.inbox("b")) == 2  # still there, just read


def test_mark_read_persists():
    mem = _mem()
    box = Postbox(mem)
    msg = box.send("a", "b", "hi")
    box.mark_read(msg)
    # A fresh Postbox over the same memory sees it as read.
    assert Postbox(mem).inbox("b")[0].read is True


def test_inbox_sorted_by_time():
    clock = {"t": 100.0}
    box = Postbox(Mycelium(InMemoryBackend(), clock=lambda: clock["t"]))
    box.send("a", "b", "first")
    clock["t"] = 200.0
    box.send("a", "b", "second")
    assert [m.body for m in box.inbox("b")] == ["first", "second"]


# --- replies + threads --------------------------------------------------------


def test_reply_swaps_sender_recipient_and_links():
    box = Postbox(_mem())
    original = box.send("alice", "bob", "can you help?", subject="help")
    reply = box.reply(original, "sure!")
    assert reply.sender == "bob"
    assert reply.recipient == "alice"
    assert reply.in_reply_to == original.id
    assert reply.subject == "Re: help"
    assert box.inbox("alice")[0].body == "sure!"


def test_thread_reconstructs_conversation_across_mailboxes():
    clock = {"t": 0.0}
    box = Postbox(Mycelium(InMemoryBackend(), clock=lambda: clock["t"]))
    m1 = box.send("a", "b", "q1")
    clock["t"] += 1
    m2 = box.reply(m1, "a1")
    clock["t"] += 1
    box.reply(m2, "q2")
    thread = box.thread(m1)
    assert [m.body for m in thread] == ["q1", "a1", "q2"]


# --- Agent shortcuts ----------------------------------------------------------


def _two_agents():
    mem = _mem()
    tree = Tree("HQ")
    a = tree.spawn(tree.root, "alice")
    b = tree.spawn(tree.root, "bob")
    return (
        Agent(a, MockBrain(replies=["x"]), memory=mem),
        Agent(b, MockBrain(replies=["x"]), memory=mem),
        a,
        b,
    )


def test_agent_send_and_inbox():
    alice, bob, a_node, b_node = _two_agents()
    alice.send(b_node, "need the pricing table", subject="pricing")
    got = bob.inbox()
    assert len(got) == 1
    assert got[0].sender == a_node.id
    assert got[0].body == "need the pricing table"


def test_agent_reply_and_fetch():
    alice, bob, a_node, b_node = _two_agents()
    alice.send(b_node, "ping")
    incoming = bob.fetch_messages()
    assert len(incoming) == 1
    bob.reply(incoming[0], "pong")
    assert alice.inbox()[0].body == "pong"
    assert bob.unread() == []  # fetch drained bob's inbox


def test_agent_messaging_noop_without_memory():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "solo")
    agent = Agent(node, MockBrain(replies=["x"]))  # no memory
    assert agent.send("someone", "hi") is None
    assert agent.inbox() == []


def test_agent_send_emits_event():
    bus = EventBus()
    collector = CollectObserver()
    bus.subscribe(collector)
    alice, bob, a_node, b_node = _two_agents()
    alice.events = bus
    alice.send(b_node, "hello")
    sent = [e for e in collector.events if e.type == MESSAGE_SENT]
    assert len(sent) == 1
    assert sent[0].payload["recipient"] == b_node.id


# --- facade -------------------------------------------------------------------


def test_org_send_and_inbox_by_department_name():
    org = Ormica("Acme")
    org.plant("business")
    # Resolve two real departments by name.
    depts = [n.name for n in org]
    src, dst = depts[1], depts[2]
    org.send(src, dst, "sync up on the launch", subject="launch")
    got = org.inbox(dst)
    assert len(got) == 1
    assert got[0].body == "sync up on the launch"
