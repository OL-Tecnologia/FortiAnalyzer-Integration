# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — FortiAnalyzer Reports (aplicacao completa)."""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

block_cipher = None


def _asset_datas():
    """Empacota assets OL, excluindo logos/tenants de clientes (LGPD)."""
    assets = ROOT / "assets"
    pairs = []
    if not assets.is_dir():
        return pairs
    for path in assets.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(assets)
        if rel.parts and rel.parts[0] == "clients":
            continue
        name = path.name.lower()
        if "cruz" in name and "logo" in name:
            continue
        dest = str(Path("assets") / rel.parent) if rel.parent != Path(".") else "assets"
        pairs.append((str(path), dest))
    return pairs


a = Analysis(
    [str(ROOT / "install" / "app_launcher.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "install" / "config.env"), "install"),
        *_asset_datas(),
    ],
    hiddenimports=[
        "forti_report",
        "forti_report.api.app",
        "forti_report.services.consolidated",
        "forti_report.charts.faz_layout",
        "forti_report.services.cycle_schedule",
        "forti_report.services.cycle_runner",
        "forti_report.services.harvest",
        "forti_report.data.harvest_catalog",
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
