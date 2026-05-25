"""Desktop entry point.

Runs uvicorn in a worker thread, opens the app in the user's default
browser, and parks a tray icon on the main thread so the friend can quit
cleanly (no Task Manager hunting). Previously embedded the UI in a
pywebview window, but pywebview's Windows backend requires the .NET 6+
Desktop Runtime via pythonnet — not present on stock Windows installs.
Falling back to the system browser drops that dependency entirely and
keeps the bundle a single-folder, no-installer affair.
"""
from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
import threading
import time
import webbrowser

import pystray
import uvicorn
from PIL import Image

from app.core.config import BUNDLE_ROOT
from app.main import app

# The lifespan in app.main opens the system browser itself on startup with a
# 1s delay. We replace that with a deterministic open *after* the socket
# accepts so there's no race with the user clicking around early.
os.environ.setdefault("FFXIV_TRADER_NO_BROWSER", "1")

log = logging.getLogger("app.desktop")

HOST = "127.0.0.1"
PREFERRED_PORT = 8000
TRAY_TITLE = "FFXIV Trader"
APP_USER_MODEL_ID = "FFXIVTrader.Desktop"
MUTEX_NAME = "Global\\FFXIVTraderInstanceMutex"

# Module-level handle so the kernel keeps the mutex alive for the lifetime of
# the process. Releasing it would let a second instance start.
_instance_mutex: int | None = None


def _claim_single_instance() -> bool:
    """Acquire a named mutex; return False if another instance already holds it.

    The OS releases the mutex when the owning process dies, so a crashed
    instance never leaves the lock held. Second exe press exits silently;
    the friend can use the tray icon of the already-running instance to
    re-open the browser tab.
    """
    global _instance_mutex
    if sys.platform != "win32":
        return True
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _instance_mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if not _instance_mutex:
        return True
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    return True


def _set_appusermodel_id() -> None:
    """Tell Windows this process is its own app, not generic Python — the
    tray icon and any future taskbar entries group under this id instead of
    pythonw.exe."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


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


def _load_tray_image() -> Image.Image:
    """Load the bundled .ico for the tray icon. Falls back to a solid yellow
    square if the file is missing so the app can still launch."""
    icon_path = BUNDLE_ROOT / "static" / "img" / "app.ico"
    if icon_path.exists():
        try:
            return Image.open(icon_path)
        except OSError:
            pass
    img = Image.new("RGB", (64, 64), (0xf5, 0xcf, 0x3d))
    return img


def main() -> int:
    if not _claim_single_instance():
        return 0
    _set_appusermodel_id()

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
    # the main thread. The tray icon owns the main thread, so disable them.
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

    webbrowser.open(url)

    image = _load_tray_image()

    def _on_open(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
        webbrowser.open(url)

    def _on_quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
        icon.visible = False
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open FFXIV Trader", _on_open, default=True),
        pystray.MenuItem("Quit", _on_quit),
    )
    tray = pystray.Icon(
        "FFXIV Trader",
        image,
        TRAY_TITLE,
        menu,
    )

    try:
        # Blocks the main thread until _on_quit calls icon.stop().
        tray.run()
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
