# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — FortiAnalyzer Reports (aplicacao completa)."""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

block_cipher = None

a = Analysis(
    [str(ROOT / "install" / "app_launcher.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "assets"), "assets"),
        (str(ROOT / "install" / "config.env"), "install"),
    ],
    hiddenimports=[
        "forti_report",
        "forti_report.api.app",
        "forti_report.runtime_paths",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "kaleido",
        "plotly",
        "plotly.graph_objects",
        "plotly.io",
        "reportlab",
        "svglib",
        "svglib.svglib",
        "lxml",
        "lxml.etree",
        "PIL",
        "httpx",
        "pydantic_settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FortiAnalyzer-Reports",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FortiAnalyzer-Reports",
)
