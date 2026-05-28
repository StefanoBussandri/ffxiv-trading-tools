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
import subprocess
import sys
import threading
import time
import traceback
import webbrowser

import pystray
import uvicorn
from PIL import Image

from app.core import heartbeat
from app.core.config import BUNDLE_ROOT, LOG_DIR, LOG_PATH, REPO_ROOT
from app.main import app

try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version
    try:
        APP_VERSION = _pkg_version("ffxiv-trader")
    except PackageNotFoundError:
        APP_VERSION = "dev"
except Exception:
    APP_VERSION = "dev"

CONTACT_INFO = "DM Stefano on Discord if anything breaks"

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

# Idle-shutdown watchdog. The frontend pings /heartbeat every ~10s, so a gap
# longer than HEARTBEAT_GRACE means every tab is gone (closed, crashed, or
# the user navigated away). The grace window is intentionally wide because
# browsers throttle setInterval in hidden/minimized tabs — Chrome can clamp
# to ~1min after a tab has been backgrounded for a while, so anything below
# ~90s risks killing the app while a real tab is still open but minimized.
# HEARTBEAT_STARTUP only controls how soon the watchdog *thread* starts
# polling; until the first beacon arrives, no shutdown can fire regardless
# (see app.core.heartbeat: last_ping starts as None).
HEARTBEAT_GRACE = 90.0
HEARTBEAT_STARTUP = 15.0
HEARTBEAT_POLL = 5.0

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

def create_uvicorn_config(app, host: str, port: int):
    """Create uvicorn config safe for desktop/no-console environments."""
    
    # Custom logging config that survives sys.stdout being None
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                # Remove colors when running headless
                "use_colors": False,
            },
            "access": {
                "format": "%(asctime)s | %(levelname)s | %(client_addr)s - %(request_line)s | %(status_code)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": False,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",  # safer than stdout
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }

    return uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,           # you already disable this
        log_config=log_config,
        use_colors=False,           # important
    )


def main() -> int:
    if not _claim_single_instance():
        return 0
    _set_appusermodel_id()

    port = _pick_port()
    url = f"http://{HOST}:{port}/"

    config = create_uvicorn_config(app, HOST, port)
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

    def _on_open_logs(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
        # `explorer /select,<file>` opens the folder with the log highlighted
        # so the friend can right-click → Send To → email without hunting.
        # Fall back to opening the dir if the file does not exist yet.
        target = LOG_PATH if LOG_PATH.exists() else LOG_DIR
        try:
            if target == LOG_PATH:
                subprocess.Popen(["explorer", f"/select,{target}"])
            else:
                subprocess.Popen(["explorer", str(target)])
        except OSError:
            pass

    def _on_about(icon: pystray.Icon, item: pystray.MenuItem) -> None:  # noqa: ARG001
        if sys.platform != "win32":
            return
        msg = (
            f"FFXIV Trader v{APP_VERSION}\n\n"
            f"Data: {REPO_ROOT}\n"
            f"Logs: {LOG_PATH}\n\n"
            f"{CONTACT_INFO}"
        )
        # Threaded MB so a wedged dialog does not lock the tray callback.
        threading.Thread(
            target=lambda: ctypes.windll.user32.MessageBoxW(
                None, msg, "About FFXIV Trader", 0x40  # MB_ICONINFORMATION
            ),
            daemon=True,
        ).start()

    menu = pystray.Menu(
        pystray.MenuItem("Open FFXIV Trader", _on_open, default=True),
        pystray.MenuItem("Open log folder", _on_open_logs),
        pystray.MenuItem("About", _on_about),
        pystray.MenuItem("Quit", _on_quit),
    )
    tray = pystray.Icon(
        "FFXIV Trader",
        image,
        TRAY_TITLE,
        menu,
    )

    def _watchdog() -> None:
        time.sleep(HEARTBEAT_STARTUP)
        while not server.should_exit:
            last = heartbeat.last_ping_monotonic()
            # None means no browser has ever phoned home — keep waiting. This
            # covers slow first-run cache bootstrap and time spent on
            # /setup.html (which loads its own heartbeat snippet, but is also
            # the page a friend might leave open while reading).
            if last is not None:
                idle = time.monotonic() - last
                if idle > HEARTBEAT_GRACE:
                    log.info("no heartbeat for %.1fs — shutting down", idle)
                    # tray.stop() unblocks tray.run() on the main thread; the
                    # finally clause below then drains uvicorn.
                    tray.stop()
                    return
            time.sleep(HEARTBEAT_POLL)

    threading.Thread(target=_watchdog, name="heartbeat-watchdog", daemon=True).start()

    try:
        # Blocks the main thread until _on_quit or the watchdog calls icon.stop().
        tray.run()
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)
    return 0


def _show_crash_dialog(exc: BaseException) -> None:
    """Pop a Windows MessageBox so a friend running the no-console build
    actually sees a crash instead of the app silently vanishing.

    The full traceback is dumped to the rotating log via logger.exception
    *before* this runs, so the dialog just needs to point them at the file.
    """
    tb_tail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-800:]
    msg = (
        f"FFXIV Trader crashed.\n\n"
        f"Log file:\n{LOG_PATH}\n\n"
        f"{CONTACT_INFO}\n\n"
        f"Last error:\n{tb_tail}"
    )
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(None, msg, "FFXIV Trader — Crash", 0x10)  # MB_ICONERROR
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        logging.getLogger("app.desktop").exception("fatal: %s", exc)
        _show_crash_dialog(exc)
        sys.exit(1)
