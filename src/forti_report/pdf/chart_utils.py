"""Embutir gráficos PNG no PDF preservando proporção."""

from __future__ import annotations

import io

from reportlab.lib.units import cm
from reportlab.platypus import Image, Spacer

# Dimensões padrão no PDF (todos os gráficos / donuts).
DONUT_MAX_HEIGHT = 7.5 * cm
BAR_MAX_HEIGHT = 7.0 * cm
GAUGE_MAX_HEIGHT = 6.2 * cm
TIMELINE_MAX_HEIGHT = 9.0 * cm
CHART_GAP = 0.22 * cm  # margem vertical entre gráficos


def embed_chart(
    png: bytes,
    *,
    max_width: float = 16 * cm,
    max_height: float = BAR_MAX_HEIGHT,
) -> Image:
    """Redimensiona imagem mantendo aspect ratio dentro dos limites."""
    img = Image(io.BytesIO(png))
    iw, ih = img.imageWidth, img.imageHeight
    if iw <= 0 or ih <= 0:
        img.drawWidth = max_width
        img.drawHeight = max_height
        return img
    scale = min(max_width / iw, max_height / ih)
    img.drawWidth = iw * scale
    img.drawHeight = ih * scale
    return img


def append_chart_with_gap(
    flow: list,
    png: bytes,
    *,
    max_width: float = 16 * cm,
    max_height: float = BAR_MAX_HEIGHT,
    gap_before: float = CHART_GAP,
    gap_after: float = CHART_GAP,
) -> None:
    """Insere gráfico com margem antes/depois (evita gráficos colados)."""
    if gap_before > 0:
        flow.append(Spacer(1, gap_before))
    flow.append(embed_chart(png, max_width=max_width, max_height=max_height))
    if gap_after > 0:
        flow.append(Spacer(1, gap_after))
