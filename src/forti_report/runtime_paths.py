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


def resolve_asset_file(rel_path: str) -> Path | None:
    """
    Localiza arquivo sob assets/:
    1) bundle (empacotado no .exe) — faixas OL, logos padrão
    2) pasta gravável ao lado do .exe — uploads de clientes
    """
    rel = (rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    if not rel.startswith("assets/"):
        return None
    for root in (bundle_root(), project_root()):
        full = (root / rel).resolve()
        try:
            full.relative_to((root / "assets").resolve())
        except ValueError:
            continue
        if full.is_file():
            return full
    return None


def bundled_config_env() -> Path | None:
    candidate = bundle_root() / "install" / "config.env"
    if candidate.is_file():
        return candidate
    dev = project_root() / "install" / "config.env"
    return dev if dev.is_file() else None
