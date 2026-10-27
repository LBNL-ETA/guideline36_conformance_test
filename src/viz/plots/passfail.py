"""Shared helpers for step-boundary annotations and the pass/fail ribbon."""

from __future__ import annotations

from typing import Optional

import plotly.graph_objects as go

from ..data.run import StepWindow


PASS_COLOR = "rgba(46, 160, 67, 0.55)"
FAIL_COLOR = "rgba(207, 34, 46, 0.55)"
UNCHECKED_COLOR = "rgba(130, 130, 130, 0.35)"

STEP_LINE_COLOR = "rgba(120, 120, 120, 0.45)"
BLOCK_LINE_COLOR = "rgba(60, 60, 60, 0.8)"
FAIL_SHADE = "rgba(207, 34, 46, 0.12)"


def _block_prefix(label: str) -> str:
    prefix = ""
    for ch in label:
        if ch.isalpha():
            prefix += ch
        else:
            break
    return prefix


def add_step_and_block_lines(
    fig: go.Figure,
    windows: list[StepWindow],
    yref: str = "paper",
    y_top: float = 1.0,
    y_bot: float = 0.0,
) -> None:
    """Add thin solid vertical lines at every step boundary; heavier line when
    the block prefix changes (AA -> BB). Anti-pattern-safe: no dashed lines."""
    if not windows:
        return

    prev_prefix: Optional[str] = None
    for w in windows:
        is_block_change = prev_prefix is not None and _block_prefix(w.label) != prev_prefix
        color = BLOCK_LINE_COLOR if is_block_change else STEP_LINE_COLOR
        width = 1.5 if is_block_change else 0.75

        fig.add_shape(
            type="line",
            xref="x",
            yref=yref,
            x0=w.t_start,
            x1=w.t_start,
            y0=y_bot,
            y1=y_top,
            line=dict(color=color, width=width),
            layer="below",
        )
        prev_prefix = _block_prefix(w.label)

    last = windows[-1]
    fig.add_shape(
        type="line",
        xref="x",
        yref=yref,
        x0=last.t_end,
        x1=last.t_end,
        y0=y_bot,
        y1=y_top,
        line=dict(color=STEP_LINE_COLOR, width=0.75),
        layer="below",
    )


def add_step_labels(
    fig: go.Figure,
    windows: list[StepWindow],
    yref: str = "paper",
    y: float = 1.02,
) -> None:
    """Annotate the midpoint of each step with its label above the plot area."""
    for w in windows:
        fig.add_annotation(
            x=(w.t_start + w.t_end) / 2 if w.t_end > w.t_start else w.t_start,
            y=y,
            xref="x",
            yref=yref,
            text=w.label,
            showarrow=False,
            font=dict(size=11, color="#000"),
            xanchor="center",
        )


def default_layout_font() -> dict:
    """Shared font/tick-color spec so every plot uses black text on white
    against Plotly's default grey axis labels."""
    return dict(
        font=dict(color="#000"),
        title_font_color="#000",
        legend=dict(font=dict(color="#000")),
        xaxis=dict(title_font=dict(color="#000"), tickfont=dict(color="#000"), linecolor="#000"),
        yaxis=dict(title_font=dict(color="#000"), tickfont=dict(color="#000"), linecolor="#000"),
    )


def add_failure_shading(
    fig: go.Figure,
    windows: list[StepWindow],
    which_steps: Optional[set[int]] = None,
    yref: str = "paper",
) -> None:
    """Shade the x-range of each failing step across the full plot height.

    If ``which_steps`` is provided, only steps whose ``step_number`` appears
    in it are shaded (used to shade only failures relevant to the currently
    plotted variable). If ``None``, shade every step where ``passed is False``.
    """
    for w in windows:
        should_shade = (
            w.passed is False if which_steps is None else w.step_number in which_steps
        )
        if not should_shade:
            continue
        fig.add_shape(
            type="rect",
            xref="x",
            yref=yref,
            x0=w.t_start,
            x1=w.t_end,
            y0=0,
            y1=1,
            fillcolor=FAIL_SHADE,
            line=dict(width=0),
            layer="below",
        )


def build_pass_fail_ribbon(windows: list[StepWindow]) -> go.Figure:
    """A one-row horizontal ribbon that colors each step by its pass/fail."""
    fig = go.Figure()
    if not windows:
        return fig

    for w in windows:
        if not w.checked:
            color = UNCHECKED_COLOR
            status = "not checked"
        elif w.passed is True:
            color = PASS_COLOR
            status = "pass"
        elif w.passed is False:
            color = FAIL_COLOR
            status = "fail"
        else:
            color = UNCHECKED_COLOR
            status = "unknown"

        x0, x1 = w.t_start, w.t_end
        if x1 <= x0:
            x1 = x0 + 0.001

        fig.add_trace(
            go.Scatter(
                x=[x0, x1, x1, x0, x0],
                y=[0, 0, 1, 1, 0],
                fill="toself",
                fillcolor=color,
                line=dict(width=0),
                mode="lines",
                showlegend=False,
                hoverinfo="text",
                text=f"{w.label} — {status}",
                name=w.label,
            )
        )
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=0.5,
            text=w.label,
            showarrow=False,
            font=dict(size=10, color="#111"),
            xanchor="center",
            yanchor="middle",
        )

    fig.update_layout(
        height=48,
        margin=dict(l=40, r=20, t=6, b=6),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            range=[0, 1],
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#000"),
    )
    return fig
