# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ffxiv-trader desktop bundle.

Output: dist/ffxiv-trader/ (onedir). The friend unzips this folder, runs
ffxiv-trader.exe, and gets the FastAPI server in a native pywebview window.
db, cache/, .env are written next to the exe → one-folder install.
"""
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

ICON_PATH = os.path.join("static", "img", "app.ico")
ICON = ICON_PATH if os.path.exists(ICON_PATH) else None

block_cipher = None

# FastAPI routers are discovered at runtime via include_router(); PyInstaller's
# static analysis misses them. Pull the whole app package in.
app_submodules = collect_submodules("app")

# uvicorn loads protocol/loop/lifespan implementations by string at runtime.
uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all("uvicorn")

# pystray ships per-platform backends (win32 / gtk / darwin / xorg) and
# picks at import time; PIL has C extensions. Collect both fully so the
# tray icon works in the frozen bundle without .NET dependencies.
pystray_datas, pystray_binaries, pystray_hiddenimports = collect_all("pystray")
pil_datas, pil_binaries, pil_hiddenimports = collect_all("PIL")

# pydantic v2 + pydantic-settings have C extensions and dynamic imports.
pydantic_datas, pydantic_binaries, pydantic_hiddenimports = collect_all("pydantic")
pydantic_settings_datas, pydantic_settings_binaries, pydantic_settings_hiddenimports = collect_all("pydantic_settings")

hiddenimports = (
    app_submodules
    + uvicorn_hiddenimports
    + pystray_hiddenimports
    + pil_hiddenimports
    + pydantic_hiddenimports
    + pydantic_settings_hiddenimports
    + [
        "aiosqlite",
        "httpx",
        "lxml",
        "lxml.etree",
        "lxml._elementpath",
        "bs4",
        "markdownify",
        "email_validator",
        "pystray._win32",
    ]
)

datas = (
    [
        ("static", "static"),
        (".env.example", "."),
    ]
    + uvicorn_datas
    + pystray_datas
    + pil_datas
    + pydantic_datas
    + pydantic_settings_datas
)

binaries = (
    uvicorn_binaries
    + pystray_binaries
    + pil_binaries
    + pydantic_binaries
    + pydantic_settings_binaries
)

a = Analysis(
    ["src/app/desktop.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pydoc",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FFXIV Trader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FFXIV Trader",
)

# PyInstaller `datas` files always land inside _internal/. We want the helper
# .bat scripts to live next to the exe so the friend can double-click them
# straight from the extracted folder, so copy them in post-COLLECT.
import shutil  # noqa: E402

_release_dir = os.path.join(DISTPATH, "FFXIV Trader")
for _aux in ("Create shortcuts.bat", "Delete shortcuts.bat"):
    _src = os.path.join(os.getcwd(), _aux)
    if os.path.exists(_src) and os.path.isdir(_release_dir):
        shutil.copy2(_src, os.path.join(_release_dir, _aux))
