"""Step drill-down: for one step, all outputs on one plot.

For each output at the selected step, draw a horizontal tolerance segment
``[expected − tol, expected + tol]`` in that output's row, a small tick at
the expected value, and a large dot at the actual value colored by pass/fail.
Rows sort with failures on top so the reader's eye lands there first.
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from ..data.run import RunHandle
from ..data.script import TestScript
from ..utils.deviation import per_step_deviation


PASS_DOT = "#54A24B"
FAIL_DOT = "#E45756"
NEUTRAL_DOT = "#888888"
BAND = "rgba(76, 120, 168, 0.28)"
EXPECTED_MARK = "#4C78A8"


def build_step_detail(
    run: RunHandle,
    script: TestScript,
    step_label: str,
    outputs: Optional[list[str]] = None,
) -> go.Figure:
    dev = per_step_deviation(run, script)
    dev_step = dev[dev["step_label"] == step_label].copy()
    if outputs is not None:
        dev_step = dev_step[dev_step["output"].isin(outputs)]

    if dev_step.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No data for {step_label}", height=200)
        return fig

    def _sort_key(row):
        if row["passed"] is False:
            return (0, row["output"])
        if row["passed"] is True:
            return (2, row["output"])
        return (1, row["output"])

    dev_step["_sort"] = dev_step.apply(_sort_key, axis=1)
    dev_step = dev_step.sort_values("_sort").reset_index(drop=True)

    ys = list(range(len(dev_step)))
    output_names = dev_step["output"].tolist()

    fig = go.Figure()

    for idx, row in dev_step.iterrows():
        y = ys[idx]
        expected = row["expected"]
        actual = row["actual"]
        tol = row["tolerance"]

        if expected is not None and tol is not None and not (isinstance(tol, float) and math.isnan(tol)) and tol > 0:
            fig.add_shape(
                type="rect",
                x0=expected - tol,
                x1=expected + tol,
                y0=y - 0.25,
                y1=y + 0.25,
                fillcolor=BAND,
                line=dict(width=0),
                layer="below",
            )
        if expected is not None:
            fig.add_trace(
                go.Scatter(
                    x=[expected],
                    y=[y],
                    mode="markers",
                    marker=dict(symbol="line-ns", size=18, color=EXPECTED_MARK, line=dict(width=2, color=EXPECTED_MARK)),
                    name="expected",
                    showlegend=(idx == 0),
                    hovertemplate=f"{row['output']}<br>expected=%{{x}}<extra></extra>",
                )
            )
        if actual is not None and not (isinstance(actual, float) and math.isnan(actual)):
            if row["passed"] is True:
                color = PASS_DOT
                status = "pass"
            elif row["passed"] is False:
                color = FAIL_DOT
                status = "fail"
            else:
                color = NEUTRAL_DOT
                status = row.get("note") or "n/a"
            fig.add_trace(
                go.Scatter(
                    x=[actual],
                    y=[y],
                    mode="markers",
                    marker=dict(
                        symbol="circle",
                        size=12,
                        color=color,
                        line=dict(width=2, color="white"),
                    ),
                    name=status,
                    showlegend=False,
                    hovertemplate=(
                        f"{row['output']}<br>actual=%{{x}}<br>"
                        f"expected={_fmt(expected)}<br>"
                        f"tol=±{_fmt(tol)}<br>{status}<extra></extra>"
                    ),
                )
            )

    fig.update_layout(
        title=dict(text=f"Step {step_label} — expected ± tolerance vs actual", font=dict(color="#000")),
        margin=dict(l=80, r=20, t=50, b=40),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#000"),
        xaxis=dict(
            title=dict(text="value", font=dict(color="#000")),
            tickfont=dict(color="#000"),
            linecolor="#000",
            showgrid=True,
            gridcolor="rgba(0,0,0,0.08)",
            zeroline=False,
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=ys,
            ticktext=output_names,
            tickfont=dict(color="#000"),
            linecolor="#000",
            autorange="reversed",
            showgrid=False,
            zeroline=False,
        ),
        showlegend=False,
        height=max(220, 40 + 34 * len(output_names)),
    )
    return fig


def _fmt(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if math.isnan(f):
        return "—"
    return f"{f:.3g}"
