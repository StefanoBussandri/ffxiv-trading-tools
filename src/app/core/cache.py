import json
from pathlib import Path
from typing import Any

from app.core.config import settings


def cache_path(name: str) -> Path:
    return settings.cache_dir / f"{name}.json"


def exists(name: str) -> bool:
    return cache_path(name).exists()


def mtime_ms(name: str) -> int | None:
    p = cache_path(name)
    if not p.exists():
        return None
    return int(p.stat().st_mtime * 1000)


def read(name: str) -> Any | None:
    p = cache_path(name)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write(name: str, data: Any) -> None:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path(name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
