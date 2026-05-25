"""Desktop entry point: uvicorn in worker thread, pywebview window on main thread.

The Windows webview backend (Edge WebView2) requires the GUI loop on the
process main thread; uvicorn therefore runs in a background thread with its
own asyncio event loop. External HTTP calls inside the FastAPI app are
already async (httpx), so long upstream waits never block the window.
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time

# Prevent the FastAPI lifespan from opening the system browser — we own the UI.
os.environ.setdefault("FFXIV_TRADER_NO_BROWSER", "1")

import uvicorn  # noqa: E402
import webview  # noqa: E402

from app.main import app  # noqa: E402

log = logging.getLogger("app.desktop")

HOST = "127.0.0.1"
PREFERRED_PORT = 8000
WINDOW_TITLE = "ffxiv-trader"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900


def _pick_port() -> int:
    """Return PREFERRED_PORT if free, otherwise an OS-assigned ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, PREFERRED_PORT))
        except OSError:
            pass
        else:
            return PREFERRED_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Block until the TCP port accepts connections, or timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((HOST, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def main() -> int:
    port = _pick_port()
    url = f"http://{HOST}:{port}/"

    config = uvicorn.Config(
        app,
        host=HOST,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    # uvicorn installs signal handlers when run() is called — only valid on
    # the main thread. We run in a worker, so disable them.
    server.install_signal_handlers = lambda: None

    server_thread = threading.Thread(
        target=server.run,
        name="uvicorn",
        daemon=True,
    )
    server_thread.start()

    if not _wait_for_server(port):
        log.error("uvicorn did not start listening on %s within timeout", url)
        return 1

    webview.create_window(
        WINDOW_TITLE,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
    )
    try:
        webview.start()
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
