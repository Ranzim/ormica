"""Tests for the LLM-facing send_message tool."""
import pytest

from ormica import Ormica, Postbox
from ormica.arbor import Tree
from ormica.brain import MockBrain, Tool, ToolCall
from ormica.mycelium import InMemoryBackend, Mycelium
from ormica.postbox import MessageToolBuilder, MessageToolConfig


def _setup():
    mem = Mycelium(InMemoryBackend())
    tree = Tree("HQ")
    alice = tree.spawn(tree.root, "alice")
    bob = tree.spawn(tree.root, "bob")
    box = Postbox(mem)
    return mem, box, alice, bob


def _builder(recipients=("bob",), resolve=None, **cfg):
    mem, box, alice, bob = _setup()
    resolve = resolve or (lambda name: bob.id)
    builder = MessageToolBuilder(
        box, alice, MessageToolConfig(recipients=recipients, **cfg), resolve=resolve
    )
    return builder, box, alice, bob


# --- config validation --------------------------------------------------------


def test_config_validation():
    with pytest.raises(ValueError):
        MessageToolConfig(recipients=())
    with pytest.raises(ValueError):
        MessageToolConfig(recipients=("bob",), max_per_turn=0)
    with pytest.raises(ValueError):
        MessageToolConfig(recipients=("bob",), max_body_chars=0)


# --- happy path ---------------------------------------------------------------


def test_send_delivers_to_recipient_and_resolves_name():
    builder, box, alice, bob = _builder()
    out = builder("bob", "need the pricing table", subject="pricing")
    assert out.startswith("ok:")
    inbox = box.inbox(bob.id)
    assert len(inbox) == 1
    assert inbox[0].sender == alice.id  # resolved name -> bob id, from alice
    assert inbox[0].body == "need the pricing table"


def test_as_tool_schema():
    builder, *_ = _builder(recipients=("bob", "carol"))
    tool = builder.as_tool()
    assert isinstance(tool, Tool)
    assert tool.name == "send_message"
    assert tool.schema["properties"]["recipient"]["enum"] == ["bob", "carol"]
    assert tool.schema["required"] == ["recipient", "body"]


# --- refusals (returned, not raised) ------------------------------------------


def test_unknown_recipient_refused():
    builder, box, alice, bob = _builder()
    out = builder("stranger", "hi")
    assert out.startswith("refused:") and "unknown recipient" in out
    assert box.inbox(bob.id) == []


def test_empty_body_refused():
    builder, *_ = _builder()
    assert builder("bob", "   ").startswith("refused:")


def test_body_too_long_refused():
    builder, *_ = _builder(max_body_chars=10)
    assert builder("bob", "x" * 11).startswith("refused:")


def test_rate_limit_refused_and_counts_malformed_calls():
    builder, box, alice, bob = _builder(max_per_turn=2)
    assert builder("stranger", "a").startswith("refused:")  # counts (1)
    assert builder("bob", "b").startswith("ok:")            # counts (2)
    out = builder("bob", "c")                                # over limit
    assert out.startswith("refused:") and "rate limit" in out
    assert len(box.inbox(bob.id)) == 1  # only the one ok send landed


def test_reset_clears_counter():
    builder, box, alice, bob = _builder(max_per_turn=1)
    builder("bob", "one")
    assert builder("bob", "two").startswith("refused:")
    builder.reset()
    assert builder("bob", "three").startswith("ok:")


def test_resolve_failure_refused():
    def bad_resolve(_name):
        raise KeyError("nope")

    builder, box, alice, bob = _builder(resolve=bad_resolve)
    assert builder("bob", "hi").startswith("refused:")


# --- runner integration -------------------------------------------------------


def test_runner_wires_send_message_tool_and_delivers():
    org = Ormica("Acme")
    org.plant("business")
    depts = [n.name for n in org][1:3]
    sender, recipient = depts[0], depts[1]

    # Declare the tool on the sender department.
    org.find(sender).meta["message_tool_config"] = MessageToolConfig(
        recipients=(recipient,)
    )

    # Brain: first call fires the tool, second returns a final answer.
    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="send_message",
                      arguments={"recipient": recipient, "body": "sync on launch"})],
            "handed off to the team",
        ]
    )
    org.task("coordinate the launch", target=sender)
    result = org.run(brain=brain)

    assert result.succeeded == 1
    delivered = org.inbox(recipient)
    assert len(delivered) == 1
    assert delivered[0].body == "sync on launch"
