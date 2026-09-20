"""Tests for typed artifacts — ArtifactType validation, parsing, grounding."""
import pytest

from ormica import Artifact, ArtifactError, ArtifactType
from ormica.arbor import Tree
from ormica.brain import MockBrain
from ormica.cortex import Constitution, artifact_oracle, grounded


# --- validation ---------------------------------------------------------------


Estimate = ArtifactType("estimate", {"cost": float, "days": int, "risks": list})


def test_valid_payload_has_no_problems():
    assert Estimate.problems({"cost": 12.5, "days": 3, "risks": ["a"]}) == []


def test_missing_field_reported():
    probs = Estimate.problems({"cost": 1.0, "days": 2})
    assert probs == ["missing required field 'risks'"]


def test_wrong_type_reported():
    probs = Estimate.problems({"cost": 1.0, "days": "soon", "risks": []})
    assert probs == ["field 'days' should be integer, got string"]


def test_bool_is_not_an_int():
    # bool subclasses int in Python; an int field must reject True.
    probs = ArtifactType("t", {"n": int}).problems({"n": True})
    assert probs == ["field 'n' should be integer, got boolean"]


def test_int_widens_to_number():
    assert ArtifactType("t", {"x": float}).problems({"x": 5}) == []


def test_optional_fields_via_required():
    T = ArtifactType("t", {"a": str, "b": str}, required=("a",))
    assert T.problems({"a": "x"}) == []
    assert T.problems({"b": "x"}) == ["missing required field 'a'"]


def test_allow_extra_toggle():
    strict = ArtifactType("t", {"a": str}, allow_extra=False)
    assert strict.problems({"a": "x", "b": 1}) == ["unexpected field 'b'"]
    loose = ArtifactType("t", {"a": str})
    assert loose.problems({"a": "x", "b": 1}) == []


def test_nested_artifact_type():
    Inner = ArtifactType("inner", {"n": int})
    Outer = ArtifactType("outer", {"inner": Inner})
    assert Outer.problems({"inner": {"n": 1}}) == []
    assert Outer.problems({"inner": {"n": "no"}}) == [
        "inner.field 'n' should be integer, got string"
    ]
    assert Outer.problems({"inner": 5}) == ["field 'inner' should be an object (inner)"]


def test_non_object_payload():
    assert ArtifactType("t", {"a": str}).problems([1, 2]) == [
        "expected an object for 't', got array"
    ]


# --- parsing ------------------------------------------------------------------


def test_parse_plain_json():
    art = Estimate.parse('{"cost": 10.0, "days": 2, "risks": []}')
    assert isinstance(art, Artifact)
    assert art.kind == "estimate"
    assert art.get("cost") == 10.0


def test_parse_strips_fence_and_prose():
    text = "Here is my estimate:\n```json\n{\"cost\": 3.0, \"days\": 1, \"risks\": [\"x\"]}\n```\nDone."
    art = Estimate.parse(text)
    assert art.get("days") == 1


def test_parse_accepts_already_parsed_dict():
    art = Estimate.parse({"cost": 1.0, "days": 1, "risks": []})
    assert art.get("cost") == 1.0


def test_parse_invalid_json_raises():
    with pytest.raises(ArtifactError, match="not valid JSON"):
        Estimate.parse("no json here")


def test_parse_validation_error_lists_problems():
    with pytest.raises(ArtifactError, match="invalid estimate: missing required field 'risks'"):
        Estimate.parse('{"cost": 1.0, "days": 2}')


# --- serialization ------------------------------------------------------------


def test_artifact_record_round_trip():
    art = Artifact(kind="estimate", data={"cost": 1.0}, meta={"author": "n1"})
    rebuilt = Artifact.from_record(art.to_record())
    assert rebuilt.kind == "estimate"
    assert rebuilt.data == {"cost": 1.0}
    assert rebuilt.meta == {"author": "n1"}


# --- grounding integration ----------------------------------------------------


def test_artifact_oracle_pass_and_fail():
    oracle = artifact_oracle(Estimate)
    assert oracle('{"cost": 1.0, "days": 1, "risks": []}', {}).ok is True
    res = oracle('{"cost": 1.0}', {})
    assert res.ok is False
    assert "missing required field 'days'" in res.reason


def test_artifact_grounding_drives_verify_retry():
    # first answer is malformed (days is a string), second is corrected.
    con = Constitution([grounded(artifact_oracle(Estimate))])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "analyst")
    from ormica import Agent

    brain = MockBrain(
        replies=[
            '{"cost": 1.0, "days": "soon", "risks": []}',
            '{"cost": 1.0, "days": 2, "risks": []}',
        ]
    )
    agent = Agent(node, brain, constitution=con)
    resp = agent.act("estimate the work")
    assert Estimate.parse(resp.content).get("days") == 2
    # the retry prompt carried the validator's reason
    assert any("should be integer" in m.content for m in brain.calls[-1])
