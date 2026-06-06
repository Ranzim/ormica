"""Basic smoke tests — the package imports and exposes its public API."""
import ormica


def test_version():
    assert ormica.__version__ == "0.1.0"


def test_public_api_exports():
    assert hasattr(ormica, "Ormica")
    assert hasattr(ormica, "Agent")
    assert hasattr(ormica, "AsyncAgent")
    assert hasattr(ormica, "Task")
    assert hasattr(ormica, "RunResult")
