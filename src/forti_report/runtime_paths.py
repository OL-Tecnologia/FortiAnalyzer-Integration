"""Caminhos do projeto (desenvolvimento ou .exe PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Pasta gravável ao lado do .exe (ou raiz do repo em dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    """Recursos empacotados dentro do .exe."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return project_root()


def frontend_dir() -> Path:
    return bundle_root() / "frontend"


def assets_dir() -> Path:
    return bundle_root() / "assets"


def bundled_config_env() -> Path | None:
    candidate = bundle_root() / "install" / "config.env"
    if candidate.is_file():
        return candidate
    dev = project_root() / "install" / "config.env"
    return dev if dev.is_file() else None
