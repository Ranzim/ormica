"""Basic smoke tests — the package imports and exposes its public API."""
import re

import ormica


_PEP440 = re.compile(
    r"^[0-9]+(\.[0-9]+)*((a|b|rc)[0-9]+)?(\.post[0-9]+)?(\.dev[0-9]+)?$"
)


def test_version():
    assert isinstance(ormica.__version__, str)
    assert _PEP440.match(ormica.__version__), (
        f"__version__ {ormica.__version__!r} is not a valid PEP 440 version"
    )


def test_public_api_exports():
    assert hasattr(ormica, "Ormica")
    assert hasattr(ormica, "Agent")
    assert hasattr(ormica, "AsyncAgent")
    assert hasattr(ormica, "Task")
    assert hasattr(ormica, "RunResult")
