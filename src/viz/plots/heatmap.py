"""Output × step deviation heatmap.

Each cell colored by normalized deviation ``|actual − expected| / tolerance``.
Values ≤ 1 mean the assertion passed; > 1 means the runner would (and did)
fail. The color ramp is a single-hue sequential (light -> dark red) with the
`1.0` contour called out as the fail threshold; cells that couldn't be
compared (ANY / expressions / init step) are drawn on a neutral gray
background and annotated.
"""

from __future__ import annotations

from typing import Optional

import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..data.run import RunHandle
from ..data.script import TestScript
from ..utils.deviation import per_step_deviation


NOT_COMPARED_BG = "rgba(200, 200, 200, 0.35)"


def _sequential_reds() -> list[list]:
    """A single-hue red ramp, light -> dark, with `1.0` mapped to a distinct step."""
    return [
        [0.00, "#FFF5F0"],
        [0.33, "#FCBBA1"],
        [0.66, "#FB6A4A"],
        [1.00, "#67000D"],
    ]


def build_heatmap(
    run: RunHandle,
    script: TestScript,
    outputs: Optional[list[str]] = None,
) -> go.Figure:
    dev = per_step_deviation(run, script)

    if outputs is None:
        outputs = list(script.outputs.columns)
    dev = dev[dev["output"].isin(outputs)]

    if dev.empty:
        fig = go.Figure()
        fig.update_layout(title="No output data for this run", height=200)
        return fig

    checked = dev[dev["note"] != "not checked (init step)"]
    checked = checked.sort_values(["step_number", "output"])

    step_labels = list(dict.fromkeys(checked["step_label"].tolist()))
    output_names = list(dict.fromkeys(checked["output"].tolist()))

    z = np.full((len(output_names), len(step_labels)), np.nan)
    text = np.full((len(output_names), len(step_labels)), "", dtype=object)
    hover = np.full((len(output_names), len(step_labels)), "", dtype=object)

    step_idx = {s: i for i, s in enumerate(step_labels)}
    out_idx = {o: i for i, o in enumerate(output_names)}

    for _, r in checked.iterrows():
        oi = out_idx[r["output"]]
        si = step_idx[r["step_label"]]
        norm = r["normalized"]
        if norm is None or (isinstance(norm, float) and math.isnan(norm)):
            z[oi][si] = np.nan
            text[oi][si] = "—"
            note = r.get("note") or "n/a"
            hover[oi][si] = f"{r['output']} · {r['step_label']}<br>{note}"
        else:
            z[oi][si] = min(float(norm), 3.0)
            text[oi][si] = f"{float(norm):.2f}"
            hover[oi][si] = (
                f"{r['output']} · {r['step_label']}<br>"
                f"expected={_fmt(r['expected'])}, actual={_fmt(r['actual'])}<br>"
                f"tolerance={_fmt(r['tolerance'])}<br>"
                f"|dev|/tol={_fmt(norm)} ({'pass' if r['passed'] else 'fail'})"
            )

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=step_labels,
            y=output_names,
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=10),
            colorscale=_sequential_reds(),
            zmin=0,
            zmax=3,
            colorbar=dict(title="|dev| / tol", tickvals=[0, 1, 2, 3], ticktext=["0", "1 (fail thresh.)", "2", "≥3"]),
            hoverinfo="text",
            hovertext=hover,
            xgap=2,
            ygap=2,
        )
    )

    fig.update_layout(
        margin=dict(l=90, r=20, t=40, b=60),
        plot_bgcolor=NOT_COMPARED_BG,
        paper_bgcolor="white",
        font=dict(color="#000"),
        xaxis=dict(
            title=dict(text="test step", font=dict(color="#000")),
            side="bottom",
            tickangle=0,
            tickfont=dict(color="#000"),
            linecolor="#000",
        ),
        yaxis=dict(
            title=dict(text="output", font=dict(color="#000")),
            autorange="reversed",
            tickfont=dict(color="#000"),
            linecolor="#000",
        ),
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
