"""Gráficos Plotly exportados como PNG (Kaleido) para embutir no PDF."""

from __future__ import annotations

import hashlib
from pathlib import Path

import plotly.graph_objects as go

from forti_report.config import get_settings

from forti_report.data.mensal_models import TimelineSlice
from forti_report.data.models import SiteRankingItem
from forti_report.data.parsers.mensal_utils import (
    bytes_to_gb,
    parse_numeric_value,
    pie_values_from_items,
    ranked_chart_values,
    timeline_has_signal,
)
from forti_report.data.wan_models import RankedItem

# Paleta corporativa (barras / destaque)
CHART_COLORS = ["#003366", "#0066A1", "#4A90C2", "#7EB6DA", "#B8D4E8"]

# Cores distintas para séries em gráficos de linha (não apenas tons de azul)
LINE_SERIES_COLORS = [
    "#E63946",  # vermelho
    "#2A9D8F",  # verde-água
    "#E9C46A",  # amarelo
    "#9B59B6",  # roxo
    "#F4A261",  # laranja
    "#1D3557",  # azul escuro
    "#06A77D",  # verde
    "#D62828",  # vermelho escuro
    "#457B9D",  # azul acinzentado
    "#8338EC",  # violeta
]

PIE_COLORS = [
    "#003366",
    "#E63946",
    "#2A9D8F",
    "#E9C46A",
    "#9B59B6",
    "#F4A261",
    "#457B9D",
    "#06A77D",
    "#8338EC",
    "#D62828",
]

# Paleta estilo FAZ (área empilhada de tráfego)
STACK_AREA_COLORS = [
    "#F4D03F",
    "#85C1E9",
    "#E67E22",
    "#E74C3C",
    "#95A5A6",
    "#F1948A",
    "#58D68D",
    "#A0522D",
    "#BB8FCE",
    "#48C9B0",
]


def top_sites_bar_chart(
    items: list[SiteRankingItem],
    *,
    title: str = "Top sites acessados",
    metric: str = "hits",
    max_items: int = 15,
) -> go.Figure:
    subset = items[:max_items]
    labels = [i.site for i in subset]
    if metric == "bandwidth_mb":
        values = [i.bandwidth_mb or 0 for i in subset]
        y_title = "Bandwidth (MB)"
    else:
        values = [i.hits or 0 for i in subset]
        y_title = "Acessos"

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=CHART_COLORS[0]),
            text=values,
            textposition="outside",
        )
    )
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        xaxis_title=y_title,
        yaxis=dict(autorange="reversed"),
        margin=dict(l=120, r=40, t=60, b=40),
        height=max(320, 28 * len(subset)),
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=11),
    )
    return fig


def chart_to_png_bytes(
    fig: go.Figure,
    *,
    width: int | None = None,
    height: int | None = None,
    cache_key: str | None = None,
    cache_scope: str | None = None,
) -> bytes:
    settings = get_settings()
    w = width or settings.pdf_chart_width
    h = int(height or fig.layout.height or 400)
    h = max(h, 220)

    cache_dir = settings.pdf_chart_cache_dir
    cache_path: Path | None = None
    if cache_key:
        cache_dir.mkdir(parents=True, exist_ok=True)
        scope_part = ""
        if cache_scope:
            from forti_report.services.mensal_cache import chart_scope_dir

            cache_dir = chart_scope_dir(settings, cache_scope)
            cache_dir.mkdir(parents=True, exist_ok=True)
            scope_part = f"{cache_scope}|"
        digest = hashlib.sha256(f"{scope_part}{cache_key}|{w}|{h}".encode()).hexdigest()[:24]
        cache_path = cache_dir / f"{digest}.png"
        if cache_path.is_file():
            return cache_path.read_bytes()

    png = fig.to_image(format="png", width=w, height=h)
    if cache_path:
        cache_path.write_bytes(png)
    return png


def top_users_bar_chart(items: list[RankedItem], *, title: str = "Top usuários") -> go.Figure | None:
    labels, values = ranked_chart_values(items, max_items=10)
    if not labels:
        return None
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker=dict(color=CHART_COLORS[1])))
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        xaxis_title="Requisições",
        yaxis=dict(autorange="reversed"),
        margin=dict(l=140, r=30, t=50, b=40),
        height=max(280, 26 * len(labels)),
        template="plotly_white",
    )
    return fig


def category_pie_chart(items: list[RankedItem], *, title: str = "Categorias") -> go.Figure | None:
    labels, values = pie_values_from_items(items)
    if not labels:
        return None
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.35, marker=dict(colors=PIE_COLORS)))
    fig.update_layout(title=dict(text=title, x=0.5), template="plotly_white", height=350)
    return fig


def bandwidth_timeline_chart(
    slices: list[TimelineSlice],
    *,
    title: str | None = None,
    max_series: int = 10,
) -> go.Figure | None:
    """Gráfico de área empilhada (estilo FAZ) — tráfego em GB por consumidor."""
    if not slices or not timeline_has_signal(slices):
        return None
    series_names: dict[str, list[float]] = {}
    labels: list[str] = []
    for sl in slices:
        labels.append(sl.label)
        for name, val in sl.values.items():
            series_names.setdefault(name, []).append(val)
    if not series_names:
        return None

    ranked = sorted(
        [(name, vals) for name, vals in series_names.items() if sum(vals) > 0],
        key=lambda x: sum(x[1]),
        reverse=True,
    )[:max_series]
    if not ranked:
        return None

    fig = go.Figure()
    n_labels = len(labels)
    for idx, (name, vals) in enumerate(ranked):
        y = vals + [0.0] * max(0, n_labels - len(vals))
        color = STACK_AREA_COLORS[idx % len(STACK_AREA_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=labels[:n_labels],
                y=[bytes_to_gb(v) for v in y[:n_labels]],
                name=name[:26],
                mode="lines",
                stackgroup="one",
                line=dict(width=0.6, color=color),
                fillcolor=color,
                hovertemplate="%{y:.2f} GB<extra></extra>",
            )
        )

    n_series = len(ranked)
    legend_rows = max(1, (n_series + 3) // 4)
    top_margin = 12 + legend_rows * 22

    fig.update_layout(
        template="plotly_white",
        height=340 + legend_rows * 16,
        legend=dict(
            orientation="h",
            y=1.0,
            yanchor="bottom",
            x=0.5,
            xanchor="center",
            font=dict(size=8),
            tracegroupgap=6,
        ),
        margin=dict(l=52, r=18, t=top_margin, b=55),
        xaxis=dict(tickangle=-45, tickfont=dict(size=8)),
        yaxis=dict(tickformat=".1f", title="Traffic (GB)"),
        hovermode="x unified",
    )
    if title:
        fig.update_layout(
            title=dict(text=title, x=0.5, xanchor="center", font=dict(size=13)),
            margin=dict(l=52, r=18, t=top_margin + 36, b=55),
            legend=dict(y=1.02),
        )
    return fig


def ranked_horizontal_chart(
    items: list[RankedItem],
    *,
    title: str,
    value_label: str = "Valor",
    max_items: int = 15,
) -> go.Figure | None:
    labels, values = ranked_chart_values(items, max_items=max_items)
    if not labels:
        return None
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=CHART_COLORS[2]),
        )
    )
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        xaxis_title=value_label,
        yaxis=dict(autorange="reversed"),
        template="plotly_white",
        height=max(280, 24 * len(labels)),
        margin=dict(l=140, r=40, t=50, b=40),
    )
    return fig


def traffic_timeline_placeholder() -> go.Figure:
    """Placeholder de tráfego WAN (substituir quando API liberar download)."""
    import plotly.graph_objects as go

    days = ["05-22", "05-23", "05-24", "05-25", "05-26", "05-27", "05-28"]
    fig = go.Figure()
    for idx, name in enumerate(["10.29.64.6", "10.29.160.6", "10.26.88.10"]):
        fig.add_trace(
            go.Scatter(
                x=days,
                y=[10 + idx * 3 + i * 2 for i in range(len(days))],
                mode="lines+markers",
                name=name,
                line=dict(color=LINE_SERIES_COLORS[idx % len(LINE_SERIES_COLORS)], width=2),
                marker=dict(size=5, color=LINE_SERIES_COLORS[idx % len(LINE_SERIES_COLORS)]),
            )
        )
    fig.update_layout(
        title="Tempo de Uso da Internet — Principais Consumidores de Banda",
        xaxis_title="Período",
        yaxis_title="Tráfego (GB)",
        template="plotly_white",
        height=280,
        legend=dict(orientation="h", y=-0.25),
    )
    return fig
