"""Caminhos de assets (bundle vs pasta gravável)."""

from pathlib import Path

from forti_report.runtime_paths import assets_dir, resolve_asset_file


def test_resolve_ol_cover_bands():
    header = resolve_asset_file("assets/img/cabecalho_capa.png")
    footer = resolve_asset_file("assets/img/rodape_capa.png")
    assert header is not None and header.is_file()
    assert footer is not None and footer.is_file()
    assert header.parent == assets_dir() / "img"


def test_resolve_rejects_path_traversal():
    assert resolve_asset_file("assets/../.env") is None
    assert resolve_asset_file("configs/clients/x.yaml") is None
