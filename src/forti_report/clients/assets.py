"""Upload e resolução de assets de branding por tenant."""

from __future__ import annotations

import re
from pathlib import Path

from forti_report.clients.models import ClientConfig, PdfClientConfig
from forti_report.clients.store import automation_password_set, get_client, save_client
from forti_report.config import Settings, get_settings
from forti_report.runtime_paths import project_root

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Upload por tenant: só logo do cliente. Faixas OL da capa são padrão fixo.
ASSET_KINDS = {
    "cover_logo": "logo",
}

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
MAX_BYTES = 5 * 1024 * 1024


class ClientAssetError(Exception):
    pass


def client_assets_dir(slug: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    if not _SLUG_RE.match(slug):
        raise ClientAssetError("slug inválido")
    root = project_root() / "assets" / "clients" / slug
    root.mkdir(parents=True, exist_ok=True)
    return root


def relative_asset_path(slug: str, filename: str) -> str:
    return f"assets/clients/{slug}/{filename}".replace("\\", "/")


def save_client_asset(
    slug: str,
    kind: str,
    *,
    filename: str,
    content: bytes,
    settings: Settings | None = None,
    update_client_config: bool = True,
) -> dict:
    """
    Grava arquivo em assets/clients/{slug}/ e atualiza o YAML do tenant (se existir).
    Retorna path relativo e kind.
    """
    settings = settings or get_settings()
    slug = slug.strip().lower()
    if kind not in ASSET_KINDS:
        raise ClientAssetError(f"kind inválido. Use: {', '.join(ASSET_KINDS)}")
    if not content:
        raise ClientAssetError("Arquivo vazio")
    if len(content) > MAX_BYTES:
        raise ClientAssetError("Arquivo maior que 5 MB")

    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ClientAssetError(
            f"Extensão não permitida ({suffix or 'sem extensão'}). Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    dest_name = f"{ASSET_KINDS[kind]}{suffix}"
    dest_dir = client_assets_dir(slug, settings)
    dest_path = dest_dir / dest_name
    dest_path.write_bytes(content)

    rel = relative_asset_path(slug, dest_name)
    client = get_client(slug, settings, include_disabled=True)
    if update_client_config and client:
        pdf_data = client.pdf.model_dump()
        pdf_data[kind] = rel
        updated = client.model_copy(update={"pdf": PdfClientConfig.model_validate(pdf_data)})
        save_client(updated, settings)
        client = updated

    return {
        "slug": slug,
        "kind": kind,
        "path": rel,
        "url": f"/api/admin/clients/{slug}/assets/{kind}",
        "client": (
            client.admin_dict(automation_password_set=automation_password_set(client, settings))
            if client
            else None
        ),
    }


def resolve_client_asset_file(client: ClientConfig, kind: str) -> Path | None:
    if kind not in ASSET_KINDS:
        return None
    rel = getattr(client.pdf, kind, "") or ""
    if not rel:
        return None
    path = Path(rel)
    if not path.is_absolute():
        path = project_root() / path
    if path.is_file():
        return path
    return None
