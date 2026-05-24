"""Refresh the mount / minion catalogue cache from FFXIVCollect.

The catalogue (which mounts/minions exist, their summoning item_id, whether that
item is tradeable) only changes on game patches. Run this after a major patch:

    python scripts/fetch_collectibles.py

Writes cache/mounts.json and cache/minions.json. The web app also populates
these on first startup if missing.
"""
import asyncio
import sys
from pathlib import Path

# Allow running as a plain script without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.clients.ffxivcollect import FFXIVCollectClient  # noqa: E402


async def main() -> None:
    client = FFXIVCollectClient()
    for kind in ("mounts", "minions"):
        rows = await client.populate(kind, force=True)
        tradeable = [r for r in rows if r["tradeable"]]
        print(f"{kind}: {len(rows)} total, {len(tradeable)} tradeable")


if __name__ == "__main__":
    asyncio.run(main())
