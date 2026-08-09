"""Minimal HTTP health server for web-service hosting platforms."""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit

LOGGER = logging.getLogger("delta_crew.health")


class HealthRequestHandler(BaseHTTPRequestHandler):
    """Serve JSON health responses without external dependencies."""

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in {"/", "/healthz"}:
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def _send_json(self, status: int, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.debug(format, *args)


def start_health_server() -> ThreadingHTTPServer | None:
    """Start Render's HTTP listener, or do nothing when ``PORT`` is unset."""
    port_value = os.getenv("PORT")
    if not port_value:
        return None

    server = ThreadingHTTPServer(("0.0.0.0", int(port_value)), HealthRequestHandler)
    Thread(target=server.serve_forever, name="health-server", daemon=True).start()
    LOGGER.info("Health server listening on port %s", server.server_port)
    return server
