"""HTTP request handler + ``serve()`` entry point for the web dashboard.

Pure stdlib (``http.server`` + ``socketserver.ThreadingMixIn``). One
connection per request; SSE clients hold their connection open and
the handler drains the per-client queue until the browser disconnects.
"""
from __future__ import annotations

import queue
import socketserver
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

from . import templates
from .observer import SSEObserver


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Threaded HTTP server — one thread per request so SSE doesn't block."""

    daemon_threads = True
    allow_reuse_address = True


class DashboardHandler(BaseHTTPRequestHandler):
    """Dispatches GET requests to one of the page renderers in ``templates``.

    The handler is configured via class attributes — ``org`` and ``sse`` —
    set by :func:`serve` before the server starts. This is the
    ``http.server``-idiomatic way to share state with the handler class.
    """

    org: Any = None
    sse: Optional[SSEObserver] = None

    # Quiet the default access-log noise; opt back in by overriding.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802 — required by BaseHTTPRequestHandler
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            self._html(templates.overview(self.org))
        elif path == "/tree":
            self._html(templates.tree(self.org))
        elif path == "/rules":
            self._html(templates.rules(self.org))
        elif path == "/signals":
            self._html(templates.signals(self.org))
        elif path == "/traces":
            self._html(templates.traces_list(self.org))
        elif path.startswith("/traces/"):
            task_id = path[len("/traces/") :]
            self._html(templates.trace_detail(self.org, task_id))
        elif path == "/events":
            self._stream_events()
        elif path == "/healthz":
            self._html("ok", content_type="text/plain")
        else:
            self.send_error(404)

    # --- helpers ------------------------------------------------------

    def _html(self, body: str, *, content_type: str = "text/html; charset=utf-8") -> None:
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _stream_events(self) -> None:
        """Server-Sent Events stream — one frame per Observer event."""
        if self.sse is None:
            self.send_error(503, "no event bus configured")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        # Disable proxy buffering so events arrive promptly.
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = self.sse.subscribe()
        try:
            # Tell the client we're alive and the stream is open.
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    payload = q.get(timeout=15.0)
                except queue.Empty:
                    # Heartbeat keeps load balancers and idle browsers happy.
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                frame = f"data: {payload}\n\n".encode("utf-8")
                try:
                    self.wfile.write(frame)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            self.sse.unsubscribe(q)


def serve(
    org: Any,
    *,
    port: int = 8000,
    host: str = "127.0.0.1",
    sse: Optional[SSEObserver] = None,
    stream=None,
) -> None:
    """Block on an HTTP server exposing the dashboard for ``org``.

    By default binds to ``127.0.0.1`` only — this dashboard has no auth
    and is **not safe for the public internet**. Pass ``host="0.0.0.0"``
    explicitly if you want to expose it on your LAN, and put it behind a
    reverse proxy with auth before exposing it anywhere else.

    Subscribes the supplied (or freshly created) :class:`SSEObserver` to
    ``org.events`` so live events flow to connected browsers.
    """
    if sse is None:
        sse = SSEObserver()
    org.subscribe(sse)

    DashboardHandler.org = org
    DashboardHandler.sse = sse

    out = stream if stream is not None else sys.stdout
    server = _ThreadingHTTPServer((host, port), DashboardHandler)
    print(
        f"ormica dashboard: http://{host}:{server.server_address[1]}  "
        "(Ctrl+C to stop)",
        file=out,
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Brief cleanup pause helps tests + ensures any in-flight SSE writes drain.
        server.shutdown()
        server.server_close()
        time.sleep(0)
