"""Tests for secret redaction — keep credentials out of persisted traces."""
import json

from ormica import redact, redact_deep
from ormica.observe import TraceObserver
from ormica.observe.trace import Trace


def test_masks_known_key_shapes():
    assert "«redacted:openai-key»" in redact("token sk-abcdefghij0123456789ABCDEF")
    assert "«redacted:anthropic-key»" in redact("key sk-ant-abcdefghij0123456789")
    assert "«redacted:google-api-key»" in redact("AIza" + "B" * 35)
    assert "«redacted:aws-access-key»" in redact("AKIAABCDEFGHIJKLMNOP")
    assert "«redacted:github-token»" in redact("ghp_" + "a" * 30)
    assert "«redacted:bearer-token»" in redact("Authorization: Bearer abcdef0123456789ghij")


def test_leaves_ordinary_text_alone():
    text = "The Matching Service pairs riders with drivers via Redis geo."
    assert redact(text) == text
    assert redact("") == "" and redact(None) is None


def test_redact_deep_walks_structures():
    payload = {
        "prompt": "my key is AIza" + "C" * 35,
        "steps": ["fine", "Bearer abcdef0123456789ghij"],
        "n": 7,
    }
    out = redact_deep(payload)
    assert "AIza" not in json.dumps(out)
    assert "«redacted:google-api-key»" in out["prompt"]
    assert "«redacted:bearer-token»" in out["steps"][1]
    assert out["n"] == 7                     # non-strings untouched


def test_trace_observer_redacts_before_persisting():
    stored = {}

    class _Store:
        def write(self, key, value, author=None):
            stored[key] = value

    secret = "AIza" + "D" * 35
    obs = TraceObserver(store=_Store())
    obs._persist(Trace(task_id="t1", result=f"here is the key {secret}"))

    blob = json.dumps(stored["traces/t1"])
    assert secret not in blob                 # the raw key never reached storage
    assert "redacted:google-api-key" in blob  # (json escapes the « » guillemets)
