"""Cabeçalho e rodapé das páginas internas (MENSAL unificado)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from reportlab.graphics import renderPM
from reportlab.graphics.shapes import Drawing, Group
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from svglib.svglib import svg2rlg

from forti_report.config import Settings, get_settings
from forti_report.pdf.page_layout import LATERAL_MARGIN

_DEFAULT_HEADER_H = 1.6 * cm
_DEFAULT_FOOTER_H = 1.2 * cm
_FOOTER_LINE_COLOR = colors.HexColor("#9B1C1C")
_FOOTER_TEXT_COLOR = colors.HexColor("#5C5C5C")
_HEADER_LOGO_MAX_W = 4.25 * cm
_HEADER_LOGO_PAD_LEFT = 0.35 * cm
_FONT_SIZE = 8
# ~2× resolução da exibição (120 pt ≈ 240 px); evita PNG gigante (milhares de px).
_LOGO_RENDER_SCALE = 2.0


@dataclass(frozen=True)
class _HeaderLogoAsset:
    reader: ImageReader
    width: float
    height: float


_logo_draw_cache: dict[tuple[str, int, int], _HeaderLogoAsset] = {}


def internal_header_height(settings: Settings, page_width: float | None = None) -> float:
    """Altura do cabeçalho interno proporcional à imagem (largura = página)."""
    pw = page_width or A4[0]
    path = _resolve_header_path(settings)
    if not path:
        return _DEFAULT_HEADER_H
    iw, ih = ImageReader(str(path)).getSize()
    if iw <= 0:
        return _DEFAULT_HEADER_H
    return pw * ih / iw


def internal_footer_height() -> float:
    return _DEFAULT_FOOTER_H


def _resolve_header_path(settings: Settings) -> Path | None:
    for candidate in (settings.pdf_internal_header_image, settings.pdf_header_image):
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=4)
def _svg_content_bounds(svg_path: str) -> tuple[float, float, float, float]:
    drawing = svg2rlg(svg_path)
    if not drawing:
        return (0.0, 0.0, 1.0, 1.0)
    return drawing.getBounds()


def _logo_layout_pt(svg_path: str, header_h: float) -> tuple[float, float]:
    x0, y0, x1, y1 = _svg_content_bounds(svg_path)
    bw = max(x1 - x0, 1.0)
    bh = max(y1 - y0, 1.0)
    max_w = min(_HEADER_LOGO_MAX_W, A4[0] * 0.24)
    max_h = header_h * 0.46
    scale = min(max_w / bw, max_h / bh)
    return bw * scale, bh * scale


def _logo_disk_path(svg_path: Path, width_pt: int) -> Path:
    settings = get_settings()
    cache_dir = settings.pdf_chart_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    mtime = int(svg_path.stat().st_mtime)
    return cache_dir / f"logo_{svg_path.stem}_{mtime}_{width_pt}.png"


@lru_cache(maxsize=8)
def _logo_png_for_width(svg_path: str, width_pt: int) -> tuple[bytes, float, float]:
    """Rasteriza SVG recortado, redimensionado ao tamanho final, fundo transparente."""
    from PIL import Image, ImageChops

    path = Path(svg_path)
    disk = _logo_disk_path(path, width_pt)
    if disk.is_file():
        data = disk.read_bytes()
        x0, y0, x1, y1 = _svg_content_bounds(svg_path)
        bw = max(x1 - x0, 1.0)
        bh = max(y1 - y0, 1.0)
        logo_w = float(width_pt)
        return data, logo_w, logo_w * bh / bw

    src = svg2rlg(svg_path)
    if not src:
        return b"", 0.0, 0.0
    x0, y0, x1, y1 = src.getBounds()
    bw = max(x1 - x0, 1.0)
    bh = max(y1 - y0, 1.0)
    logo_w = float(width_pt)
    logo_h = logo_w * bh / bw

    cropped = Drawing(bw, bh)
    group = Group()
    group.add(src)
    group.translate(-x0, -y0)
    cropped.add(group)

    im = renderPM.drawToPIL(cropped, dpi=72, bg=0xFFFFFF)
    target_w = max(1, int(round(logo_w * _LOGO_RENDER_SCALE)))
    target_h = max(1, int(round(logo_h * _LOGO_RENDER_SCALE)))
    if im.size != (target_w, target_h):
        im = im.resize((target_w, target_h), Image.Resampling.LANCZOS)

    r, g, b = im.convert("RGB").split()
    threshold = 240

    def _light(ch: Image.Image) -> Image.Image:
        return ch.point(lambda p: 255 if p >= threshold else 0)

    white = ImageChops.multiply(_light(r), ImageChops.multiply(_light(g), _light(b)))
    alpha = white.point(lambda p: 0 if p == 255 else 255)
    im = im.convert("RGBA")
    im.putalpha(alpha)

    buf = BytesIO()
    im.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    disk.write_bytes(data)
    return data, logo_w, logo_h


def _header_logo_asset(settings: Settings, *, header_h: float) -> _HeaderLogoAsset | None:
    path = settings.pdf_header_logo_image
    if not path.is_file():
        return None

    logo_w, logo_h = _logo_layout_pt(str(path), header_h)
    width_key = int(round(logo_w))
    header_key = int(round(header_h))
    cache_key = (str(path.resolve()), width_key, header_key)
    cached = _logo_draw_cache.get(cache_key)
    if cached:
        return cached

    png, logo_w, logo_h = _logo_png_for_width(str(path), width_key)
    if not png:
        return None

    reader = ImageReader(BytesIO(png))
    asset = _HeaderLogoAsset(reader=reader, width=logo_w, height=logo_h)
    _logo_draw_cache[cache_key] = asset
    return asset


def prewarm_header_logo(settings: Settings, *, header_h: float) -> None:
    """Gera/cacheia o PNG do logo antes do multiBuild (evita pico na 1ª página)."""
    _header_logo_asset(settings, header_h=header_h)


def _draw_header_logo(canvas, settings: Settings, *, header_h: float) -> None:
    asset = _header_logo_asset(settings, header_h=header_h)
    if not asset:
        return

    _, ph = A4
    x = LATERAL_MARGIN + _HEADER_LOGO_PAD_LEFT
    y = ph - header_h + (header_h - asset.height) / 2
    canvas.drawImage(
        asset.reader,
        x,
        y,
        width=asset.width,
        height=asset.height,
        mask="auto",
        preserveAspectRatio=True,
    )


def draw_internal_page_header(canvas, settings: Settings, *, header_h: float) -> None:
    path = _resolve_header_path(settings)
    if not path:
        return
    pw, ph = A4
    canvas.drawImage(
        str(path),
        0,
        ph - header_h,
        width=pw,
        height=header_h,
        mask="auto",
    )
    _draw_header_logo(canvas, settings, header_h=header_h)


def draw_internal_page_footer(
    canvas,
    *,
    adom: str,
    page_num: int,
    total_pages: int,
    footer_h: float,
) -> None:
    pw, _ = A4
    x0 = LATERAL_MARGIN
    x1 = pw - LATERAL_MARGIN
    line_y = footer_h

    canvas.setStrokeColor(_FOOTER_LINE_COLOR)
    canvas.setLineWidth(1.2)
    canvas.line(x0, line_y, x1, line_y)

    canvas.setFont("Helvetica", _FONT_SIZE)
    canvas.setFillColor(_FOOTER_TEXT_COLOR)
    text_y = line_y - _FONT_SIZE - 1
    total = max(total_pages, page_num, 1)
    canvas.drawString(x0, text_y, f"RELATORIO MENSAL GERAL — {adom}")
    canvas.drawRightString(x1, text_y, f"Página {page_num} de {total}")
