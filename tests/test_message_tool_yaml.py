"""Tests for message_tool: colony YAML support (parity with emit_tool)."""
from pathlib import Path

import pytest

from ormica import Ormica
from ormica.brain import MockBrain, ToolCall
from ormica.colony import load_colony
from ormica.postbox import MessageToolConfig


def _load(tmp_path: Path, body: str):
    yml = tmp_path / "c.yaml"
    yml.write_text(body)
    return load_colony(yml)


# --- parsing ------------------------------------------------------------------


def test_yaml_compact_form_recipients_only(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: eng
    role: e
    message_tool: [sales, support]
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    cfg = node.meta["message_tool_config"]
    assert isinstance(cfg, MessageToolConfig)
    assert cfg.recipients == ("sales", "support")
    assert cfg.max_per_turn == 3  # default


def test_yaml_explicit_mapping_form(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: eng
    role: e
    message_tool:
      recipients: [sales]
      max_per_turn: 5
      max_body_chars: 500
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    cfg = node.meta["message_tool_config"]
    assert cfg.recipients == ("sales",)
    assert cfg.max_per_turn == 5
    assert cfg.max_body_chars == 500


def test_yaml_no_message_tool_field_means_no_meta_entry(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: plain
    role: p
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert "message_tool_config" not in node.meta


def test_yaml_mapping_without_recipients_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="must include a 'recipients'"):
        _load(tmp_path, """
name: x
templates:
  - name: eng
    message_tool:
      max_per_turn: 2
""")


def test_yaml_invalid_type_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="must be a list .* or a mapping"):
        _load(tmp_path, """
name: x
templates:
  - name: eng
    message_tool: 42
""")


# --- end-to-end through the runner --------------------------------------------


def test_runtime_send_message_tool_from_yaml(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: sales
    role: s
  - name: eng
    role: e
    task: coordinate with sales
    message_tool: [sales]
""")
    org = Ormica("X", max_depth=3)
    cls().plant(org)
    org.task("kick off the launch", target="eng")

    brain = MockBrain(replies=[
        [ToolCall(id="c1", name="send_message",
                  arguments={"recipient": "sales", "body": "sync on launch"})],
        "handed off to sales",
    ])
    result = org.run(brain=brain)
    assert result.succeeded == 1
    delivered = org.inbox("sales")
    assert len(delivered) == 1
    assert delivered[0].body == "sync on launch"
