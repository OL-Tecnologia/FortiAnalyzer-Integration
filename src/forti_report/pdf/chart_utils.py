"""Embutir gráficos PNG no PDF preservando proporção."""

from __future__ import annotations

import io

from reportlab.lib.units import cm
from reportlab.platypus import Image


def embed_chart(
    png: bytes,
    *,
    max_width: float = 16 * cm,
    max_height: float = 8 * cm,
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
