# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ffxiv-trader desktop bundle.

Output: dist/ffxiv-trader/ (onedir). The friend unzips this folder, runs
ffxiv-trader.exe, and gets the FastAPI server in a native pywebview window.
db, cache/, .env are written next to the exe → one-folder install.
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# FastAPI routers are discovered at runtime via include_router(); PyInstaller's
# static analysis misses them. Pull the whole app package in.
app_submodules = collect_submodules("app")

# uvicorn loads protocol/loop/lifespan implementations by string at runtime.
uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all("uvicorn")

# pywebview ships per-platform backends loaded by string.
webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")

# pydantic v2 + pydantic-settings have C extensions and dynamic imports.
pydantic_datas, pydantic_binaries, pydantic_hiddenimports = collect_all("pydantic")
pydantic_settings_datas, pydantic_settings_binaries, pydantic_settings_hiddenimports = collect_all("pydantic_settings")

hiddenimports = (
    app_submodules
    + uvicorn_hiddenimports
    + webview_hiddenimports
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
    ]
)

datas = [
    ("static", "static"),
    (".env.example", "."),
] + uvicorn_datas + webview_datas + pydantic_datas + pydantic_settings_datas

binaries = uvicorn_binaries + webview_binaries + pydantic_binaries + pydantic_settings_binaries

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
    name="ffxiv-trader",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ffxiv-trader",
)
