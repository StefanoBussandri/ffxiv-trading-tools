"""Reset ffxiv-trader to a fresh-user state for testing the first-run flow.

Moves data.db (+ WAL files) and cache/ into a timestamped backup folder —
nothing is deleted, so the old data can be restored. The next launch then
behaves as a brand-new install: first-run setup screen + full cache rebuild.

Stop the app before running, or the database files stay locked.

    python scripts/reset_data.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_FILES = ["data.db", "data.db-wal", "data.db-shm", "data.db-journal"]


def main() -> int:
    print("=" * 60)
    print(" ffxiv-trader - reset to fresh-user state")
    print("=" * 60)
    print()
    print("Moves into a timestamped backup folder (NOT deleted):")
    print("  - data.db  (and -wal / -shm / -journal)")
    print("  - cache/   (all cached game data + items.json)")
    print()
    print("IMPORTANT: stop the app first, or the database files stay locked.")
    print()
    if input("Proceed? (y/N): ").strip().lower() != "y":
        print("Cancelled.")
        return 0

    backup = ROOT / "reset-backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup.mkdir(parents=True, exist_ok=True)

    moved = 0
    failed: list[str] = []

    def _move(src: Path, dst: Path) -> None:
        nonlocal moved
        try:
            shutil.move(str(src), str(dst))
            moved += 1
        except OSError as e:
            failed.append(f"{src.name} ({e})")

    for name in DB_FILES:
        src = ROOT / name
        if src.exists():
            _move(src, backup / name)

    cache = ROOT / "cache"
    if cache.exists():
        _move(cache, backup / "cache")

    print()
    if moved == 0 and not failed:
        try:
            backup.rmdir()
        except OSError:
            pass
        print("Nothing to move — already in a fresh state.")
        return 0

    if failed:
        print("WARNING: could not move — is the app still running?")
        for f in failed:
            print(f"  - {f}")
        print()

    print(f"Moved {moved} item(s) to: {backup}")
    print()
    print("To restore the old data later:")
    print(f"  - move data.db* from '{backup}' back to the project root")
    print(f"  - move '{backup / 'cache'}' back to 'cache'")
    print("Or delete the backup folder if the old data is not needed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
