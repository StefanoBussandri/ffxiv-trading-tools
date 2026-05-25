"""Desktop entry point: uvicorn in worker thread, pywebview window on main thread.

The Windows webview backend (Edge WebView2) requires the GUI loop on the
process main thread; uvicorn therefore runs in a background thread with its
own asyncio event loop. External HTTP calls inside the FastAPI app are
already async (httpx), so long upstream waits never block the window.
"""
from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
import threading
import time
from ctypes import wintypes

# Prevent the FastAPI lifespan from opening the system browser — we own the UI.
os.environ.setdefault("FFXIV_TRADER_NO_BROWSER", "1")

import uvicorn  # noqa: E402
import webview  # noqa: E402

from app.core.config import BUNDLE_ROOT  # noqa: E402
from app.main import app  # noqa: E402

log = logging.getLogger("app.desktop")

HOST = "127.0.0.1"
PREFERRED_PORT = 8000
WINDOW_TITLE = "FFXIV Trader"
WINDOW_WIDTH = 1500
WINDOW_HEIGHT = 900

# Module-level handle so the kernel keeps the mutex alive for the lifetime of
# the process. Releasing it would let a second instance start.
_instance_mutex: int | None = None
APP_USER_MODEL_ID = "FFXIVTrader.Desktop"
MUTEX_NAME = "Global\\FFXIVTraderInstanceMutex"


def _claim_single_instance() -> bool:
    """Acquire a named mutex; return False if another instance already holds it.

    Uses a Windows kernel object so the check survives process crashes (the OS
    cleans up the mutex when the owning process dies). The second exe press is
    a no-op — bringing the existing window to the foreground reliably from
    another process triggers a WebView2 repaint bug that leaves the window
    blank, so a silent exit is the safer behaviour.
    """
    global _instance_mutex
    if sys.platform != "win32":
        return True
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _instance_mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if not _instance_mutex:
        return True  # fall through — better to allow than to fail silently
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    return True


def _set_appusermodel_id() -> None:
    """Tell Windows this process is its own app, not generic Python.

    Without this the taskbar groups the window under the Python icon. The
    string is opaque — any unique app id works.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def _find_own_window() -> int | None:
    """Enumerate top-level windows and return the first visible, titled HWND
    that belongs to this process. The pywebview window is the only candidate
    in our process, but we still filter to avoid grabbing a console handle on
    a misconfigured build."""
    user32 = ctypes.windll.user32
    own_pid = os.getpid()
    found = ctypes.c_void_p(0)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _cb(hwnd: int, _lparam: int) -> bool:
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != own_pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindowTextLengthW(hwnd) <= 0:
            return True
        found.value = hwnd
        return False  # stop enumeration

    user32.EnumWindows(_cb, 0)
    return int(found.value) if found.value else None


def _on_window_ready() -> None:
    """Callback fired by pywebview after the window is created. Pins the
    application icon to the native window so it shows up in the taskbar."""
    if sys.platform != "win32":
        return
    # The native window can take a moment to register; poll briefly.
    hwnd = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        hwnd = _find_own_window()
        if hwnd:
            break
        time.sleep(0.1)
    if not hwnd:
        return
    _apply_window_icon(hwnd)


def _apply_window_icon(hwnd: int) -> None:
    """Pywebview defaults to its own logo for the window/taskbar icon. Override
    by loading the bundled .ico and posting WM_SETICON to the native window."""
    icon_path = BUNDLE_ROOT / "static" / "img" / "app.ico"
    if not icon_path.exists():
        return
    user32 = ctypes.windll.user32
    LR_LOADFROMFILE = 0x00000010
    LR_DEFAULTSIZE = 0x00000040
    IMAGE_ICON = 1
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    flags = LR_LOADFROMFILE | LR_DEFAULTSIZE
    hicon = user32.LoadImageW(None, str(icon_path), IMAGE_ICON, 0, 0, flags)
    if not hicon:
        return
    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)


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
    if not _claim_single_instance():
        return 0  # graceful no-op — focused the existing window instead
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
        # webview.start(func) runs func in a worker after the window is up,
        # which is where we can safely poke the native HWND.
        webview.start(_on_window_ready)
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
