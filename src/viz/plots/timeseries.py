"""Time-series plot: trajectories with expected-value markers + tolerance bands.

For each selected output, we draw the actual as a solid line and one
"expected" marker per test step (⊗ — circle-x) placed at the step's
**end time**, which is when the runner's ``assert_output`` actually
evaluates. A thin grey rectangle just before ``t_end`` at the tolerance
extent (``[expected ± tol]``, or half-open for inequality expected
values) visualises the accept region **at the moment of evaluation**
— crucial because a signal ramping toward its target during a step
should not be judged "in-tolerance" for the whole step duration.

All expected markers share one legend entry ("Expected value") and all
tolerance bands share one ("Tolerance band"), regardless of how many
outputs are plotted.

Expected values from the test script may be a plain number, an inequality
(``>=50``, ``<=71``, ``>0``, ``<10``) — drawn as a marker at the threshold
with a half-open band extending to the plot edge in the acceptable
direction — or a variable reference (``=OtherVar``) — evaluated by
reading ``OtherVar``'s recorded value at that step's end. ``=ANY`` and
Excel expressions the runner evaluates dynamically (``INTERPOLATE``,
``RAMP``, ``LAST``) are skipped without a marker.

Steps where an output actually failed are shaded red across the plot's
full height. Step boundaries are marked with thin vertical lines; block
changes (A → B) use a heavier line and the step label sits above the plot.

Inputs (as opposed to outputs) get only the actual line — there is no
expected/tolerance to draw.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from ..data.run import RunHandle, StepWindow
from ..data.script import TestScript
from ..utils.deviation import per_step_deviation
from .passfail import (
    add_failure_shading,
    add_step_and_block_lines,
    add_step_labels,
)


SAFE_PALETTE = [
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#E45756",
    "#72B7B2",
    "#EECA3B",
    "#B279A2",
    "#FF9DA6",
]

EXPECTED_MARKER_COLOR = "#000000"
TOLERANCE_BAND_FILL = "rgba(160, 160, 160, 0.28)"

_EXPECTED_LEGEND_GROUP = "expected"
_TOLERANCE_LEGEND_GROUP = "tolerance"


@dataclass
class ExpectedSpec:
    """One step's expected value for one output, parsed into a form the
    plotter can render: a marker location plus a tolerance-band extent
    (either two-sided or one-sided).

    ``lower`` / ``upper`` = ``None`` means the band is open in that direction
    (drawn to the plot's y-axis edge). ``value`` = the marker's y position.
    """

    value: float
    lower: Optional[float]
    upper: Optional[float]
    kind: str


_INEQ_RE = re.compile(r"^\s*(>=|<=|>|<)\s*([-+]?\d+(?:\.\d+)?)\s*$")


def _resolve_expected(
    script: TestScript,
    values: pd.DataFrame,
    w: StepWindow,
    name: str,
) -> Optional[ExpectedSpec]:
    if w.label not in script.outputs.index:
        return None
    raw = script.outputs.loc[w.label].get(name)
    tol = script.tolerances.get(name)
    tol_f = float(tol) if tol is not None and not (isinstance(tol, float) and math.isnan(tol)) else 0.0

    if raw is None:
        return None

    if not isinstance(raw, str):
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        if math.isnan(v):
            return None
        return ExpectedSpec(value=v, lower=v - tol_f, upper=v + tol_f, kind="exact")

    s = raw.strip()
    if not s or "ANY" in s:
        return None

    m = _INEQ_RE.match(s)
    if m:
        op, thresh = m.group(1), float(m.group(2))
        if op in (">=", ">"):
            return ExpectedSpec(value=thresh, lower=thresh - tol_f, upper=None, kind=op)
        return ExpectedSpec(value=thresh, lower=None, upper=thresh + tol_f, kind=op)

    if s.startswith("=") and "(" not in s and "LAST" not in s:
        ref = s[1:].strip()
        if ref in values.columns:
            sub = values[values["time"] <= w.t_end + 1e-6]
            if sub.empty:
                sub = values.iloc[[0]]
            v = _try_float_scalar(sub.iloc[-1][ref])
            if v is not None:
                return ExpectedSpec(
                    value=v, lower=v - tol_f, upper=v + tol_f, kind=f"ref:{ref}"
                )

    return None


def _try_float_scalar(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def _plot_y_edges(values: pd.DataFrame, variables: list[str]) -> tuple[float, float]:
    """Return (lo, hi) that comfortably encloses the actual traces so one-sided
    tolerance bands (from ``>=X`` / ``<=X`` expected values) can extend visibly
    to the edge of the plot without inflating the y-axis to ±infinity."""
    lows, highs = [], []
    for name in variables:
        if name in values.columns:
            col = pd.to_numeric(values[name], errors="coerce").dropna()
            if not col.empty:
                lows.append(float(col.min()))
                highs.append(float(col.max()))
    if not lows:
        return -1.0, 1.0
    lo, hi = min(lows), max(highs)
    span = hi - lo if hi > lo else max(abs(hi), 1.0)
    return lo - 0.5 * span, hi + 0.5 * span


def build_timeseries(
    run: RunHandle,
    script: TestScript,
    variables: list[str],
    windows: Optional[list[StepWindow]] = None,
    time_range: Optional[tuple[float, float]] = None,
    show_expected: bool = True,
    show_tolerance: bool = True,
) -> go.Figure:
    values = run.load_values()
    windows = windows or run.step_windows(script)

    dev = per_step_deviation(run, script, windows)

    values_t_max = float(values["time"].max()) if not values.empty else 0.0
    windows_t_max = max((w.t_end for w in windows), default=0.0)
    total_time = max(values_t_max, windows_t_max)
    full_range = (0.0, total_time)

    y_edge_low, y_edge_high = _plot_y_edges(values, variables)

    fig = go.Figure()

    tolerance_shown_in_legend = False
    expected_shown_in_legend = False

    for i, name in enumerate(variables):
        if name not in values.columns:
            continue
        color = SAFE_PALETTE[i % len(SAFE_PALETTE)]
        is_output = name in script.outputs.columns

        fig.add_trace(
            go.Scatter(
                x=values["time"],
                y=values[name],
                mode="lines",
                line=dict(color=color, width=2),
                name=name,
                legendgroup=name,
                hovertemplate=f"{name}<br>t=%{{x:.1f}}s<br>value=%{{y}}<extra></extra>",
            )
        )

        if not (is_output and show_expected):
            continue

        for w in windows:
            spec = _resolve_expected(script, values, w, name)
            if spec is None:
                continue

            step_duration = max(w.t_end - w.t_start, 0.0)
            band_width = min(total_time * 0.01, step_duration * 0.5) if step_duration > 0 else 0.0
            band_x_start = w.t_end - band_width
            band_x_end = w.t_end

            if show_tolerance and band_width > 0 and (spec.lower is not None or spec.upper is not None):
                lower = spec.lower if spec.lower is not None else y_edge_low
                upper = spec.upper if spec.upper is not None else y_edge_high
                fig.add_trace(
                    go.Scatter(
                        x=[band_x_start, band_x_end, band_x_end, band_x_start, band_x_start],
                        y=[lower, lower, upper, upper, lower],
                        fill="toself",
                        fillcolor=TOLERANCE_BAND_FILL,
                        line=dict(width=0),
                        mode="lines",
                        name="Tolerance band",
                        legendgroup=_TOLERANCE_LEGEND_GROUP,
                        showlegend=not tolerance_shown_in_legend,
                        hoverinfo="skip",
                    )
                )
                tolerance_shown_in_legend = True

            fig.add_trace(
                go.Scatter(
                    x=[w.t_end],
                    y=[spec.value],
                    mode="markers",
                    marker=dict(
                        symbol="circle-x",
                        size=14,
                        color="white",
                        line=dict(color=EXPECTED_MARKER_COLOR, width=2),
                    ),
                    name="Expected value",
                    legendgroup=_EXPECTED_LEGEND_GROUP,
                    showlegend=not expected_shown_in_legend,
                    hovertemplate=(
                        f"{name} · {w.label}<br>"
                        f"expected {spec.kind} %{{y}}<extra></extra>"
                    ),
                )
            )
            expected_shown_in_legend = True

    add_step_and_block_lines(fig, windows)
    add_step_labels(fig, windows)

    fail_step_numbers = {
        int(r["step_number"])
        for _, r in dev.iterrows()
        if r["output"] in variables and r["passed"] is False
    }
    if fail_step_numbers:
        add_failure_shading(fig, windows, which_steps=fail_step_numbers)

    layout = dict(
        margin=dict(l=60, r=20, t=40, b=48),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="left",
            x=0,
            font=dict(color="#000"),
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        hovermode="x unified",
        font=dict(color="#000"),
        xaxis=dict(
            title=dict(text="time (s since test start)", font=dict(color="#000")),
            tickfont=dict(color="#000"),
            linecolor="#000",
            showgrid=True,
            gridcolor="rgba(0,0,0,0.08)",
            zeroline=False,
        ),
        yaxis=dict(
            tickfont=dict(color="#000"),
            title_font=dict(color="#000"),
            linecolor="#000",
            showgrid=True,
            gridcolor="rgba(0,0,0,0.08)",
            zeroline=False,
        ),
    )
    layout["xaxis"]["range"] = list(time_range) if time_range is not None else list(full_range)
    fig.update_layout(**layout)

    return fig
