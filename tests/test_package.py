"""Basic smoke test — the package imports and has a version."""
import ormica


def test_version():
    assert ormica.__version__ == "0.0.1"
