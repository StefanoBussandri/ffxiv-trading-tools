"""Browser-tab heartbeat tracker.

Frontend pings /heartbeat on a timer and on pagehide (via sendBeacon). The
desktop entry-point's watchdog reads `last_ping_monotonic()` to decide when
to shut the process down — no live tab + grace window elapsed = nobody is
using it, exit instead of squatting in the background.

State is a simple float guarded by a lock so the asyncio request handler
and the desktop watchdog thread can read/write without coordination.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_last_ping = time.monotonic()


def touch() -> None:
    """Mark the moment a heartbeat arrived."""
    global _last_ping
    with _lock:
        _last_ping = time.monotonic()


def last_ping_monotonic() -> float:
    with _lock:
        return _last_ping
