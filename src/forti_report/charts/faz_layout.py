"""Desenha no PDF o mesmo tipo de gráfico que o FortiAnalyzer usa no relatório original."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import plotly.graph_objects as go

from forti_report.charts.plotly_charts import LINE_SERIES_COLORS, PIE_COLORS, STACK_AREA_COLORS

class ChartLike(Protocol):
    kind: str
    headers: list[str]
    rows: list[list[str]]


_GRAPHIC_KINDS = {"pie", "line", "area", "bar", "stackbar", "bubble", "bubble-ring"}
_TIME = re.compile(r"^\d{10}$")
_CLOCK = re.compile(r"^(\d+):(\d{2}):(\d{2})$")


def is_graphic(table: ChartLike) -> bool:
    return table.kind in _GRAPHIC_KINDS and bool(table.rows)


def figure_for_chart(table: ChartLike) -> go.Figure | None:
    if not is_graphic(table):
        return None
    if table.kind == "pie":
        return _pie(table, hole=0)
    if table.kind == "bubble-ring":
        return _pie(table, hole=0.46)
    if table.kind == "bubble":
        return _bars(table)
    if table.kind in {"line", "area"}:
        return _series(table, stacked=table.kind == "area")
    if table.kind == "stackbar":
        return _stacked_bars(table)
    return _bars(table)


def render_faz_chart(table: ChartLike) -> tuple[bytes, int, int] | None:
    fig = figure_for_chart(table)
    if fig is None:
        return None
    width = 720
    height = int(fig.layout.height or 360)
    png = fig.to_image(format="png", width=width, height=height)
    return png, width, height


def _pie(table: ChartLike, *, hole: float) -> go.Figure | None:
    labels, values = _top_slices(*_pairs(table))
    if len(labels) < 1 or not any(values):
        return None
    total = sum(values) or 1
    legend = [f"{label}  {100 * value / total:.1f}%" for label, value in zip(labels, values)]
    texts = [f"{100 * value / total:.1f}%" if value / total >= 0.08 else "" for value in values]
    fig = go.Figure(
        go.Pie(
            labels=legend,
            values=values,
            hole=hole,
            sort=False,
            marker=dict(colors=_cycle(PIE_COLORS, len(labels))),
            text=texts,
            textinfo="text",
            textposition="inside",
        )
    )
    _layout(fig, 250)
    fig.update_traces(textfont_size=14)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, x=1.02, font=dict(size=12)),
        margin=dict(l=4, r=150, t=8, b=8),
    )
    return fig


def _series(table: ChartLike, *, stacked: bool) -> go.Figure | None:
    points = [row for row in table.rows if row and _TIME.match(row[0].strip())]
    value_cols = [index for index in _numeric_columns(table) if index != 0]
    points = _trim_empty_edges(points, value_cols)
    if len(points) < 2 or not value_cols:
        return _bars(table)
    zone = ZoneInfo("America/Sao_Paulo")
    xs = [datetime.fromtimestamp(int(row[0]), zone) for row in points]
    series = [
        [_measure(row[index]) if index < len(row) else None for row in points]
        for index in value_cols
    ]
    series, unit = _scale_series(series)
    fig = go.Figure()
    colors = STACK_AREA_COLORS if stacked else LINE_SERIES_COLORS
    for nth, index in enumerate(value_cols):
        name = table.headers[index] if index < len(table.headers) and table.headers[index] else f"Série {nth + 1}"
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=series[nth],
                name=name,
                mode="lines",
                stackgroup="one" if stacked else None,
                line=dict(width=2, color=colors[nth % len(colors)]),
                fill="tonexty" if stacked else None,
            )
        )
    _layout(fig, 360, legend_below=True)
    fig.update_layout(xaxis_title="", yaxis_title=unit, hovermode="x unified")
    fig.update_xaxes(tickformat="%d/%m")
    return fig


def _bars(table: ChartLike) -> go.Figure | None:
    labels, values = _pairs(table)
    if not labels or not any(values):
        return None
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)[:15]
    labels = [labels[i] for i in order][::-1]
    values = [values[i] for i in order][::-1]
    divisor, unit = _unit_for(max(values) if values else 0)
    values = [value / divisor for value in values]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color="#003366"),
        )
    )
    _layout(fig, max(280, 26 * len(labels) + 80))
    fig.update_layout(showlegend=False, xaxis_title=unit, margin=dict(l=160, r=24, t=12, b=32))
    return fig


def _stacked_bars(table: ChartLike) -> go.Figure | None:
    text_cols = [i for i in range(len(table.headers)) if i not in _numeric_columns(table)]
    value_cols = _numeric_columns(table)
    if len(text_cols) >= 2 and value_cols:
        group_col, stack_col = text_cols[0], text_cols[1]
        value_col = value_cols[0]
        groups: list[str] = []
        stacks: dict[str, dict[str, float]] = {}
        for row in table.rows:
            group = row[group_col] if group_col < len(row) else ""
            stack = row[stack_col] if stack_col < len(row) else ""
            value = _measure(row[value_col]) if value_col < len(row) else None
            if not group or value is None:
                continue
            if group not in stacks:
                groups.append(group)
                stacks[group] = {}
            stacks[group][stack] = stacks[group].get(stack, 0) + value
        names = list(dict.fromkeys(name for group in groups for name in stacks[group]))
        if groups and names:
            names = names[:8]
            columns = [[stacks[group].get(name, 0) for group in groups] for name in names]
            peak = max((value for column in columns for value in column), default=0)
            divisor, unit = _unit_for(peak)
            fig = go.Figure()
            for nth, name in enumerate(names):
                fig.add_trace(
                    go.Bar(
                        name=name,
                        x=groups,
                        y=[value / divisor for value in columns[nth]],
                        marker=dict(color=PIE_COLORS[nth % len(PIE_COLORS)]),
                    )
                )
            fig.update_layout(barmode="stack", yaxis_title=unit)
            _layout(fig, 360, legend_below=True)
            return fig
    return _bars(table)


def _bubbles(table: ChartLike) -> go.Figure | None:
    labels, values = _pairs(table)
    if not labels or not any(values):
        return None
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)[:12]
    labels = [labels[i] for i in order]
    values = [values[i] for i in order]
    size_max = max(values) or 1
    fig = go.Figure(
        go.Scatter(
            x=list(range(len(labels))),
            y=values,
            mode="markers+text",
            text=labels,
            textposition="top center",
            marker=dict(
                size=[18 + 42 * (value / size_max) for value in values],
                color=_cycle(PIE_COLORS, len(labels)),
                line=dict(width=1, color="#ffffff"),
            ),
        )
    )
    _layout(fig, 380)
    fig.update_layout(
        showlegend=False,
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis_title="",
    )
    return fig


def _pairs(table: ChartLike) -> tuple[list[str], list[float]]:
    numbers = _numeric_columns(table)
    if not numbers:
        return [], []
    value_col = _prefer_amount(table, numbers)
    label_cols = [index for index in range(len(table.headers)) if index not in numbers]
    labels: list[str] = []
    values: list[float] = []
    for row in table.rows:
        if value_col >= len(row):
            continue
        measure = _measure(row[value_col])
        if measure is None:
            continue
        parts = [row[index] for index in label_cols if index < len(row) and row[index].strip()]
        labels.append(" — ".join(parts) or f"Item {len(labels) + 1}")
        values.append(measure)
    return labels, values


def _prefer_amount(table: ChartLike, columns: list[int]) -> int:
    for index in columns:
        header = table.headers[index].lower() if index < len(table.headers) else ""
        if "%" not in header:
            return index
    return columns[0]


def _numeric_columns(table: ChartLike) -> list[int]:
    found: list[int] = []
    width = max((len(row) for row in table.rows), default=0)
    for index in range(width):
        values = [row[index] for row in table.rows if index < len(row) and row[index].strip()]
        if not values:
            continue
        parsed = [_measure(value) for value in values]
        if sum(item is not None for item in parsed) >= max(1, len(values) // 2):
            if not all(_TIME.match(value.strip()) for value in values):
                found.append(index)
    return found


def _times(table: ChartLike) -> list[datetime]:
    if not table.rows or not table.rows[0]:
        return []
    raw = [row[0].strip() for row in table.rows if row and row[0].strip()]
    if not raw or sum(bool(_TIME.match(value)) for value in raw) < len(raw) // 2:
        return []
    zone = ZoneInfo("America/Sao_Paulo")
    return [datetime.fromtimestamp(int(value), zone) for value in raw if _TIME.match(value)]


def _top_slices(labels: list[str], values: list[float], limit: int = 10) -> tuple[list[str], list[float]]:
    if len(labels) <= limit:
        return labels, values
    order = sorted(range(len(values)), key=lambda index: values[index], reverse=True)
    keep, rest = order[:limit], order[limit:]
    return (
        [labels[index] for index in keep] + ["Outros"],
        [values[index] for index in keep] + [sum(values[index] for index in rest)],
    )


def _trim_empty_edges(points: list[list[str]], columns: list[int]) -> list[list[str]]:
    def alive(row: list[str]) -> bool:
        for index in columns:
            if index < len(row) and (_measure(row[index]) or 0) > 0:
                return True
        return False

    start = 0
    while start < len(points) and not alive(points[start]):
        start += 1
    end = len(points)
    while end > start and not alive(points[end - 1]):
        end -= 1
    trimmed = points[start:end]
    return trimmed if len(trimmed) >= 2 else points


def _unit_for(peak: float) -> tuple[float, str]:
    if peak >= 1_000_000_000:
        return 1_000_000_000, "GB"
    if peak >= 1_000_000:
        return 1_000_000, "MB"
    if peak >= 10_000:
        return 1_000, "mil"
    return 1, ""


def _scale_series(series: list[list[float | None]]) -> tuple[list[list[float | None]], str]:
    peak = max((value or 0 for column in series for value in column), default=0)
    divisor, unit = _unit_for(peak)
    if divisor == 1:
        return series, unit
    return [[None if value is None else value / divisor for value in column] for column in series], unit


def _group_labels(labels: list[str], values: list[float]) -> tuple[list[str], list[float]]:
    grouped: dict[str, float] = {}
    order: list[str] = []
    for label, value in zip(labels, values):
        key = label.split(" — ")[0].strip() or label
        if key not in grouped:
            order.append(key)
            grouped[key] = 0
        grouped[key] += value
    ranked = sorted(order, key=lambda name: grouped[name], reverse=True)
    return ranked, [grouped[name] for name in ranked]


def _measure(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    clock = _CLOCK.match(text)
    if clock:
        hours, minutes, seconds = (int(part) for part in clock.groups())
        return float(hours * 3600 + minutes * 60 + seconds)
    text = text.replace(" ", "")
    factor = 1.0
    upper = text.upper()
    for suffix, multiplier in (
        ("TB", 1_000_000_000_000),
        ("GB", 1_000_000_000),
        ("MB", 1_000_000),
        ("KB", 1_000),
        ("G", 1_000_000_000),
        ("M", 1_000_000),
        ("K", 1_000),
    ):
        if upper.endswith(suffix):
            factor = multiplier
            text = text[: -len(suffix)]
            upper = text.upper()
            break
    if text.endswith("%"):
        text = text[:-1]
    if text.count(",") > 1 or ("," in text and "." in text):
        text = text.replace(",", "")
    elif text.count(",") == 1 and "." not in text:
        left, right = text.split(",")
        text = left + right if len(right) == 3 else f"{left}.{right}"
    try:
        return float(text) * factor
    except ValueError:
        return None


def _plain_ticks(fig: go.Figure) -> None:
    for axis_name, key in (("xaxis", "x"), ("yaxis", "y")):
        peak = 0.0
        saw_number = False
        saw_time = False
        for trace in fig.data:
            for item in getattr(trace, key, None) or []:
                if isinstance(item, datetime):
                    saw_time = True
                elif isinstance(item, (int, float)) and not isinstance(item, bool):
                    saw_number = True
                    peak = max(peak, abs(float(item)))
        if saw_number and not saw_time and peak >= 10_000:
            fig.update_layout(**{axis_name: dict(tickformat=".2s", exponentformat="SI")})


def _cycle(colors: list[str], count: int) -> list[str]:
    return [colors[index % len(colors)] for index in range(count)]


def _layout(fig: go.Figure, height: int, *, legend_below: bool = False) -> None:
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=11),
        height=height + (28 if legend_below else 0),
        margin=dict(l=48, r=24, t=12, b=78 if legend_below else 40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.22, x=0),
    )
