"""Caminhos do instalador (script ou .exe PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def install_dir() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS) / "install"
    return Path(__file__).resolve().parent


def frontend_dir() -> Path:
    return install_dir() / "frontend"


def config_env_path() -> Path:
    bundled = install_dir() / "config.env"
    if bundled.is_file():
        return bundled
    return project_root() / "install" / "config.env"


def venv_python() -> Path:
    return project_root() / ".venv" / "Scripts" / "python.exe"
