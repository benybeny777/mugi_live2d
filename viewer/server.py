"""Serve the repository-local Live2D QA viewer without external uploads."""

from __future__ import annotations

import argparse
import contextlib
import http.server
import socket
import socketserver
import urllib.error
import urllib.request
import webbrowser
from functools import partial
from pathlib import Path

HOST = "127.0.0.1"
START_PORT = 8765
REPOSITORY = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve repository files and keep pythonw startup silent."""

    def log_message(self, format: str, *args: object) -> None:
        """Suppress console logging because the launcher intentionally has no console."""


class ReusableThreadingServer(socketserver.ThreadingTCPServer):
    """Local threaded server that can be restarted immediately."""

    allow_reuse_address = True


def _is_existing_viewer(port: int) -> bool:
    """Return whether an already-running viewer answers on the expected URL."""
    try:
        url = f"http://{HOST}:{port}/viewer/index.html"
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _available_port() -> int:
    """Choose a local port without binding to an external interface."""
    for port in range(START_PORT, START_PORT + 20):
        with contextlib.closing(socket.socket()) as candidate:
            try:
                candidate.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("Live2D viewer用の空きポートがありません")


def main() -> None:
    """Open the existing viewer or start a new local-only server."""
    parser = argparse.ArgumentParser(description="Serve the local Mugi Live2D viewer")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser")
    args = parser.parse_args()
    if _is_existing_viewer(START_PORT):
        if not args.no_browser:
            webbrowser.open(f"http://{HOST}:{START_PORT}/viewer/index.html")
        return
    port = _available_port()
    handler = partial(QuietHandler, directory=str(REPOSITORY))
    with ReusableThreadingServer((HOST, port), handler) as server:
        if not args.no_browser:
            webbrowser.open(f"http://{HOST}:{port}/viewer/index.html")
        server.serve_forever()


if __name__ == "__main__":
    main()
