"""Data-source integrations — external systems of record.

Currently ships the :mod:`~ormica.integrations.data.github` integration::

    from ormica.integrations.data import github

    tools = github.all_tools()
"""
from ormica.integrations.data import github

__all__ = ["github"]
