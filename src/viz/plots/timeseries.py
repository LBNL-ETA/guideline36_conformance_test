"""Time-series plot: trajectories with expected-value markers + tolerance
error bars, arranged as stacked subplots grouped by unit.

Layout
------
Variables sharing a unit (from the point-map's ``Unit`` column, which
matches ``unit_in_test`` in ``point_properties.csv``) stack into the same
subplot so their magnitudes are directly comparable. Any variable named
in ``isolate`` is pulled into its own subplot even if others share its
unit — useful when the user wants the expected/tolerance for one signal
to dominate the row. Variables with no unit fall into a single
"(unitless)" bucket at the bottom.

For each output, the actual is drawn as a solid line and one "expected"
marker per test step (⊗ — circle-x) is placed at the step's **end time**,
which is when the runner's ``assert_output`` actually evaluates.

Tolerance glyph (F3)
--------------------
At each step's ``t_end`` we draw a vertical error bar rooted at the
expected value:

* **Exact expected** (``v``): whisker ``v-tol → v+tol``; horizontal
  dash cap (``line-ew``) at each finite bound.
* **Inequality expected** (``>=v`` / ``>v``): dash cap at ``v-tol``
  (closed side, below); upward-pointing triangle arrow at
  ``v + 0.15·y_span`` (open side).
* **Inequality expected** (``<=v`` / ``<v``): dash cap at ``v+tol``
  (closed side, above); downward-pointing triangle arrow at
  ``v − 0.15·y_span`` (open side).
* When a side's whisker length is zero (``tol == 0`` on the closed
  side, or a strict inequality that starts at the expected value),
  that side is skipped — just the marker, or marker + arrow.

All expected markers share one legend entry ("Expected value") and all
tolerance glyphs share one ("Tolerance"), regardless of how many
outputs or subplots are shown.

Overlays
--------
Steps where an output actually failed are shaded red across the plot's
full height. Step boundaries are marked with thin vertical lines; block
changes (A → B) use a heavier line and the step label sits above the
topmost subplot. These overlays use ``yref="paper"`` so they span every
subplot.

Inputs (as opposed to outputs) get only the actual line — there is no
expected/tolerance to draw.
"""

from __future__ import annotations

import math
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
TOLERANCE_GLYPH_COLOR = "rgba(90, 90, 90, 0.9)"
UNITLESS_LABEL = "(unitless)"
ARROW_OPEN_FRACTION = 0.15

_EXPECTED_LEGEND_GROUP = "expected"
_TOLERANCE_LEGEND_GROUP = "tolerance"


@dataclass
class ExpectedSpec:
    """One step's expected value for one output, parsed into a form the
    plotter can render: a marker location plus a tolerance-band extent
    (either two-sided or one-sided).

    ``lower`` / ``upper`` = ``None`` means the band is open in that direction
    (drawn as an arrow pointing outward). ``value`` = the marker's y position.
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
    """Return (lo, hi) that comfortably encloses the actual traces so
    one-sided (inequality) tolerance arrows land inside the plot area."""
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


def _unit_for(pointmap: Optional[pd.DataFrame], name: str) -> str:
    """Return the stripped unit string for ``name`` from the point map, or
    an empty string if not found or blank."""
    if pointmap is None or name not in pointmap.index:
        return ""
    u = pointmap.loc[name].get("unit")
    if u is None:
        return ""
    s = str(u).strip()
    return "" if s.lower() in ("", "none", "nan") else s


def _group_variables(
    variables: list[str],
    pointmap: Optional[pd.DataFrame],
    isolate: Optional[list[str]],
) -> list[tuple[str, list[str]]]:
    """Return list of ``(group_label, [variables])`` in row order.

    Rules:

    * Every variable in ``isolate`` gets its own group, labeled
      ``"<var> (<unit>)"`` when a unit is known, else just ``"<var>"``.
    * Remaining variables group by unit (stripped, case-insensitive).
    * Empty/None units collapse into a single ``(unitless)`` bucket.
    * Isolated groups appear first in the order the user selected them;
      grouped-by-unit rows follow, sorted alphabetically by unit;
      ``(unitless)`` is always last.
    """
    isolate_set = set(isolate or [])
    groups: list[tuple[str, list[str]]] = []

    for name in variables:
        if name in isolate_set:
            unit = _unit_for(pointmap, name)
            label = f"{name} ({unit})" if unit else name
            groups.append((label, [name]))

    by_unit: OrderedDict[str, list[str]] = OrderedDict()
    for name in variables:
        if name in isolate_set:
            continue
        unit = _unit_for(pointmap, name) or UNITLESS_LABEL
        by_unit.setdefault(unit, []).append(name)

    def _sort_key(unit: str) -> tuple[int, str]:
        return (1, "") if unit == UNITLESS_LABEL else (0, unit.lower())

    for unit in sorted(by_unit.keys(), key=_sort_key):
        groups.append((unit, by_unit[unit]))

    return groups


def _add_tolerance_errorbar(
    fig: go.Figure,
    *,
    x: float,
    spec: ExpectedSpec,
    y_edge: tuple[float, float],
    row: int,
    show_legend_entry: bool,
) -> bool:
    """Draw the error-bar tolerance glyph at ``x`` for one (step, output).

    Returns ``True`` if a legend-visible trace was added (so the caller
    can suppress subsequent duplicates). Layout:

    * Whisker: vertical line from ``lower`` to ``upper`` (or between the
      value and the arrow tip on the open side of an inequality).
    * Closed terminal: ``line-ew`` marker (horizontal dash).
    * Open terminal (inequality): ``triangle-up`` / ``triangle-down`` at
      the value ± ``ARROW_OPEN_FRACTION * y_span``.

    Sides whose whisker length is zero (e.g. ``tol == 0`` on the closed
    side of an exact expected) are skipped.
    """
    v = spec.value
    y_lo, y_hi = y_edge
    y_span = y_hi - y_lo if y_hi > y_lo else max(abs(y_hi), 1.0)
    open_ext = ARROW_OPEN_FRACTION * y_span

    # Lower side
    lower_finite = spec.lower is not None
    upper_finite = spec.upper is not None
    lower_end = spec.lower if lower_finite else v - open_ext
    upper_end = spec.upper if upper_finite else v + open_ext
    draw_lower = lower_end < v - 1e-12
    draw_upper = upper_end > v + 1e-12

    legend_used = False

    def _next_show() -> bool:
        nonlocal legend_used
        if show_legend_entry and not legend_used:
            legend_used = True
            return True
        return False

    line_kw = dict(color=TOLERANCE_GLYPH_COLOR, width=2)
    marker_line_kw = dict(color=TOLERANCE_GLYPH_COLOR, width=2)

    if draw_lower:
        fig.add_trace(
            go.Scatter(
                x=[x, x],
                y=[lower_end, v],
                mode="lines",
                line=line_kw,
                name="Tolerance",
                legendgroup=_TOLERANCE_LEGEND_GROUP,
                showlegend=_next_show(),
                hoverinfo="skip",
            ),
            row=row,
            col=1,
        )
        if lower_finite:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[lower_end],
                    mode="markers",
                    marker=dict(
                        symbol="line-ew",
                        size=14,
                        color=TOLERANCE_GLYPH_COLOR,
                        line=marker_line_kw,
                    ),
                    name="Tolerance",
                    legendgroup=_TOLERANCE_LEGEND_GROUP,
                    showlegend=_next_show(),
                    hoverinfo="skip",
                ),
                row=row,
                col=1,
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[lower_end],
                    mode="markers",
                    marker=dict(
                        symbol="triangle-down",
                        size=12,
                        color=TOLERANCE_GLYPH_COLOR,
                    ),
                    name="Tolerance",
                    legendgroup=_TOLERANCE_LEGEND_GROUP,
                    showlegend=_next_show(),
                    hoverinfo="skip",
                ),
                row=row,
                col=1,
            )

    if draw_upper:
        fig.add_trace(
            go.Scatter(
                x=[x, x],
                y=[v, upper_end],
                mode="lines",
                line=line_kw,
                name="Tolerance",
                legendgroup=_TOLERANCE_LEGEND_GROUP,
                showlegend=_next_show(),
                hoverinfo="skip",
            ),
            row=row,
            col=1,
        )
        if upper_finite:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[upper_end],
                    mode="markers",
                    marker=dict(
                        symbol="line-ew",
                        size=14,
                        color=TOLERANCE_GLYPH_COLOR,
                        line=marker_line_kw,
                    ),
                    name="Tolerance",
                    legendgroup=_TOLERANCE_LEGEND_GROUP,
                    showlegend=_next_show(),
                    hoverinfo="skip",
                ),
                row=row,
                col=1,
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[upper_end],
                    mode="markers",
                    marker=dict(
                        symbol="triangle-up",
                        size=12,
                        color=TOLERANCE_GLYPH_COLOR,
                    ),
                    name="Tolerance",
                    legendgroup=_TOLERANCE_LEGEND_GROUP,
                    showlegend=_next_show(),
                    hoverinfo="skip",
                ),
                row=row,
                col=1,
            )

    return legend_used


def build_timeseries(
    run: RunHandle,
    script: TestScript,
    variables: list[str],
    windows: Optional[list[StepWindow]] = None,
    time_range: Optional[tuple[float, float]] = None,
    show_expected: bool = True,
    show_tolerance: bool = True,
    pointmap: Optional[pd.DataFrame] = None,
    isolate: Optional[list[str]] = None,
) -> go.Figure:
    values = run.load_values()
    windows = windows or run.step_windows(script)

    dev = per_step_deviation(run, script, windows)

    values_t_max = float(values["time"].max()) if not values.empty else 0.0
    windows_t_max = max((w.t_end for w in windows), default=0.0)
    total_time = max(values_t_max, windows_t_max)
    full_range = (0.0, total_time)

    plottable = [v for v in variables if v in values.columns]
    groups = _group_variables(plottable, pointmap, isolate)
    n_rows = max(len(groups), 1)

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
    )

    tolerance_shown_in_legend = False
    expected_shown_in_legend = False
    palette_i = 0

    for r_idx, (group_label, group_vars) in enumerate(groups, start=1):
        y_edge = _plot_y_edges(values, group_vars)

        for name in group_vars:
            color = SAFE_PALETTE[palette_i % len(SAFE_PALETTE)]
            palette_i += 1
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
                ),
                row=r_idx,
                col=1,
            )

            if not (is_output and show_expected):
                continue

            for w in windows:
                spec = _resolve_expected(script, values, w, name)
                if spec is None:
                    continue

                if show_tolerance:
                    added = _add_tolerance_errorbar(
                        fig,
                        x=w.t_end,
                        spec=spec,
                        y_edge=y_edge,
                        row=r_idx,
                        show_legend_entry=not tolerance_shown_in_legend,
                    )
                    if added:
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
                    ),
                    row=r_idx,
                    col=1,
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

    subplot_height = 260 + 220 * max(0, n_rows - 1)

    fig.update_layout(
        height=subplot_height,
        margin=dict(l=60, r=20, t=48, b=48),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25 / max(n_rows, 1),
            xanchor="left",
            x=0,
            font=dict(color="#000"),
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        hovermode="x unified",
        font=dict(color="#000"),
    )

    xaxis_range = list(time_range) if time_range is not None else list(full_range)

    for r_idx in range(1, n_rows + 1):
        xaxis_key = "xaxis" if r_idx == 1 else f"xaxis{r_idx}"
        yaxis_key = "yaxis" if r_idx == 1 else f"yaxis{r_idx}"
        fig.update_layout(
            **{
                xaxis_key: dict(
                    range=xaxis_range,
                    title=dict(
                        text="time (s since test start)" if r_idx == n_rows else "",
                        font=dict(color="#000"),
                    ),
                    tickfont=dict(color="#000"),
                    linecolor="#000",
                    showgrid=True,
                    gridcolor="rgba(0,0,0,0.08)",
                    zeroline=False,
                ),
                yaxis_key: dict(
                    title=dict(
                        text=groups[r_idx - 1][0] if groups else "",
                        font=dict(color="#000"),
                    ),
                    tickfont=dict(color="#000"),
                    linecolor="#000",
                    showgrid=True,
                    gridcolor="rgba(0,0,0,0.08)",
                    zeroline=False,
                ),
            }
        )

    return fig
