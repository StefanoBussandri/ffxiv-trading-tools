"""Browser-tab heartbeat tracker.

Frontend pings /heartbeat on a timer and the desktop entry-point's watchdog
reads `last_ping_monotonic()` to decide when to shut the process down — no
live tab + grace window elapsed = nobody is using it, exit instead of
squatting in the background.

The clock starts as None and only flips to a real timestamp once the first
beacon arrives. That way the watchdog cannot mis-fire during slow first-run
startup (where `populate_initial_cache` can hold off lifespan completion
long enough that no page can even hit /heartbeat yet) or while the user is
sitting on /setup.html. The watchdog treats None as "no one has connected
yet, keep waiting".
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_last_ping: float | None = None


def touch() -> None:
    """Mark the moment a heartbeat arrived."""
    global _last_ping
    with _lock:
        _last_ping = time.monotonic()


def last_ping_monotonic() -> float | None:
    """Return the monotonic timestamp of the last heartbeat, or None if none yet."""
    with _lock:
        return _last_ping
