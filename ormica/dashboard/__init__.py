"""
dashboard — a tiny stdlib-only web dashboard for an Ormica colony.

Renders tree, signals, rules, and stored traces as server-side HTML;
streams live events to the browser via Server-Sent Events. No build
chain, no extra dependencies — ``http.server`` and ``queue.Queue``
only.

::

    from ormica.dashboard import serve
    serve(org, port=8000)

Or from the CLI::

    ormica dashboard --config ormica.yaml --port 8000

Wire it into ``ormica run`` to watch the colony think live, or point
it at a config whose ``memory_db`` already has traces in it to browse
a finished run.
"""

from .observer import SSEObserver
from .server import DashboardHandler, serve

__all__ = ["DashboardHandler", "SSEObserver", "serve"]
