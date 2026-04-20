"""Local HTTP server for the built llmwiki site.

Uses only Python stdlib. Binds to 127.0.0.1 by default so nothing is exposed
to the network unless the user explicitly passes --host 0.0.0.0.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import webbrowser
from pathlib import Path


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Like SimpleHTTPRequestHandler but with prettier logs."""

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Suppress per-request logs for a cleaner terminal.
        return


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def serve_site(
    directory: Path,
    port: int = 8765,
    host: str = "127.0.0.1",
    open_browser: bool = False,
) -> int:
    directory = directory.expanduser().resolve()
    if not directory.exists():
        print(f"error: {directory} does not exist. Run `llmwiki build` first.")
        return 2
    os.chdir(directory)
    url = f"http://{host}:{port}/"
    print(f"==> Serving {directory} at {url}")
    print("    Press Ctrl+C to stop.")
    try:
        with _ReusableTCPServer((host, port), _QuietHandler) as httpd:
            if open_browser:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n  stopped.")
    except OSError as e:
        print(f"error: could not bind {host}:{port}: {e}")
        return 1
    return 0
