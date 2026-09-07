"""Streamlit entrypoint for the viz UI.

Run with ``streamlit run <path-to-this-file>`` — the ``g36conftest-viz``
console script wraps that call. The launcher may pass ``--run=<run_dir>`` on
the streamlit CLI to preselect a run; it also honors a ``?run=`` URL
query-param.
"""

from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from viz.data.discover import (
    find_project_root,
    list_runs,
    resolve_script_and_pointmap,
    resolved_device_type,
)
from viz.data.pointmap import load_pointmap
from viz.data.run import RunHandle
from viz.data.script import TestScript, load_test_script
from viz.plots.heatmap import build_heatmap
from viz.plots.passfail import build_pass_fail_ribbon
from viz.plots.stepdetail import build_step_detail
from viz.plots.timeseries import build_timeseries
from viz.utils.deviation import per_step_deviation


st.set_page_config(page_title="G36 conformance viz", layout="wide")


@st.cache_data(show_spinner=False)
def _cached_load_pointmap(path: str) -> pd.DataFrame:
    return load_pointmap(path)


@st.cache_data(show_spinner=False)
def _cached_load_script(
    path: str, ip_header: str, cond_header: str, op_header: str
) -> TestScript:
    return load_test_script(
        path,
        input_points_header=ip_header,
        conditions_header=cond_header,
        output_points_header=op_header,
    )


@st.cache_data(show_spinner=False)
def _cached_load_values(csv_path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def _values_for(run: RunHandle) -> pd.DataFrame:
    p = run.values_path
    return _cached_load_values(str(p), p.stat().st_mtime)


def _parse_argv() -> dict:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--run", default=None)
    parser.add_argument("--project-root", default=None)
    known, _unknown = parser.parse_known_args(sys.argv[1:])
    return vars(known)


def _preselected_run_dir(argv: dict) -> Optional[Path]:
    q = st.query_params.get("run") if hasattr(st, "query_params") else None
    candidate = argv.get("run") or q
    if not candidate:
        return None
    p = Path(candidate)
    return p if p.exists() else None


def _label_option(short: str, long_name: Optional[str], use_long: bool) -> str:
    if use_long and long_name:
        return f"{long_name} ({short})"
    return short


def _block_prefix(label: str) -> str:
    prefix = ""
    for ch in label:
        if ch.isalpha():
            prefix += ch
        else:
            break
    return prefix


def _grouped_by_test_type(runs: list[RunHandle]) -> OrderedDict[str, list[RunHandle]]:
    out: OrderedDict[str, list[RunHandle]] = OrderedDict()
    for r in runs:
        out.setdefault(r.test_type, []).append(r)
    return out


def _on_run_radio_change(test_type: str) -> None:
    """Streamlit ``on_change`` callback: whichever expander's radio the user
    just touched wins — its current value becomes the app-wide selection."""
    st.session_state.selected_run_key = st.session_state[f"radio_run_{test_type}"]


def _pick_run_sidebar(runs: list[RunHandle], preselect_key: Optional[str]) -> RunHandle:
    """Grouped run picker: one collapsible ``st.expander`` per test_type,
    each with a ``st.radio`` for its runs. All radios update the same
    ``selected_run_key`` via ``on_change`` — no follow-up button press
    needed to activate a selection made in a non-current group.
    """
    if "selected_run_key" not in st.session_state or (
        preselect_key and st.session_state.selected_run_key != preselect_key
    ):
        st.session_state.selected_run_key = preselect_key or runs[0].key

    groups = _grouped_by_test_type(runs)
    st.markdown("### Run")
    for test_type, group_runs in groups.items():
        selected_in_group = any(r.key == st.session_state.selected_run_key for r in group_runs)
        with st.expander(
            f"**{test_type}** — {len(group_runs)} run{'s' if len(group_runs) != 1 else ''}",
            expanded=selected_in_group,
        ):
            options = [r.key for r in group_runs]
            widget_key = f"radio_run_{test_type}"
            if widget_key not in st.session_state:
                if selected_in_group:
                    st.session_state[widget_key] = st.session_state.selected_run_key
                else:
                    st.session_state[widget_key] = options[0]
            elif selected_in_group and st.session_state[widget_key] != st.session_state.selected_run_key:
                st.session_state[widget_key] = st.session_state.selected_run_key
            st.radio(
                f"runs_{test_type}",
                options=options,
                format_func=lambda k: k.split("/", 1)[1],
                key=widget_key,
                on_change=_on_run_radio_change,
                args=(test_type,),
                label_visibility="collapsed",
            )

    key = st.session_state.selected_run_key
    return next(r for r in runs if r.key == key)


def _on_filter_radio_change(block: str) -> None:
    """Streamlit ``on_change`` callback: whichever block-expander radio the
    user just touched wins — its current value becomes the app-wide filter."""
    picked = st.session_state[f"radio_filter_{block}"]
    if picked == f"Whole block {block}":
        st.session_state.filter_choice = ("block", block)
    else:
        st.session_state.filter_choice = ("step", picked)


def _pick_block_or_step_filter(windows) -> tuple[str, Optional[str]]:
    """Return ('all', None) | ('block', block_letter) | ('step', step_label).

    Renders an "Show everything" toggle then one collapsible ``st.expander``
    per block letter, each with a radio for that block's steps plus a
    "Whole block <X>" option. Selection is single-choice across all radios
    via a shared ``st.session_state.filter_choice`` updated by ``on_change``.
    """
    st.markdown("### Filter")

    block_to_steps: OrderedDict[str, list[str]] = OrderedDict()
    for w in windows:
        p = _block_prefix(w.label)
        if not p:
            continue
        block_to_steps.setdefault(p, []).append(w.label)

    if "filter_choice" not in st.session_state:
        st.session_state.filter_choice = ("all", None)

    show_all = st.checkbox(
        "Show everything",
        value=(st.session_state.filter_choice[0] == "all"),
        key="filter_show_all",
    )
    if show_all:
        st.session_state.filter_choice = ("all", None)
        return "all", None

    for block, steps in block_to_steps.items():
        this_group_selected = (
            st.session_state.filter_choice == ("block", block)
            or (
                st.session_state.filter_choice[0] == "step"
                and st.session_state.filter_choice[1] in steps
            )
        )
        with st.expander(f"Block **{block}** — {len(steps)} steps", expanded=this_group_selected):
            options = [f"Whole block {block}"] + steps
            widget_key = f"radio_filter_{block}"
            if widget_key not in st.session_state:
                if st.session_state.filter_choice == ("block", block):
                    st.session_state[widget_key] = options[0]
                elif (
                    st.session_state.filter_choice[0] == "step"
                    and st.session_state.filter_choice[1] in steps
                ):
                    st.session_state[widget_key] = st.session_state.filter_choice[1]
                else:
                    st.session_state[widget_key] = options[0]
            st.radio(
                f"filter_{block}",
                options=options,
                key=widget_key,
                on_change=_on_filter_radio_change,
                args=(block,),
                label_visibility="collapsed",
            )

    return st.session_state.filter_choice


def main() -> None:
    argv = _parse_argv()
    project_root = Path(argv["project_root"]) if argv.get("project_root") else find_project_root()

    runs = list_runs(project_root)
    if not runs:
        st.title("G36 conformance viz")
        st.warning(
            f"No runs found under {project_root}/conformance_tests/*/results/. "
            f"Run a test with `save_csv: true` first."
        )
        return

    preselect = _preselected_run_dir(argv)
    preselect_key = None
    if preselect:
        for r in runs:
            if r.run_dir == preselect.resolve():
                preselect_key = r.key
                break

    device_type = resolved_device_type(project_root)

    with st.sidebar:
        run = _pick_run_sidebar(runs, preselect_key)

    excel_path, pointmap_path, test_section = resolve_script_and_pointmap(
        project_root, run.test_type, device_type=device_type
    )
    pointmap = _cached_load_pointmap(str(pointmap_path))
    script = _cached_load_script(
        str(excel_path),
        test_section.get("input_points_header", "BACnet Inputs"),
        test_section.get("conditions_header", "Conditions for Evaluation of Test Step"),
        test_section.get("output_points_header", "BACnet Expected Outputs"),
    )

    windows = run.step_windows(script)

    with st.sidebar:
        st.markdown("### View")
        plot_type = st.radio(
            "Plot type",
            options=["Time series", "Deviation heatmap", "Step drill-down"],
            index=0,
        )
        io_choice = st.radio(
            "Signals",
            options=["Both inputs and outputs", "Inputs only", "Outputs only"],
            index=2,
        )
        use_long = st.checkbox("Show long names", value=False)

        filter_choice = _pick_block_or_step_filter(windows)

    values_cols = set(_values_for(run).columns)
    input_names = [c for c in script.inputs.columns if c in values_cols]
    output_names = [c for c in script.outputs.columns if c in values_cols]

    if io_choice == "Inputs only":
        available = input_names
    elif io_choice == "Outputs only":
        available = output_names
    else:
        available = input_names + output_names

    label_map = {
        s: _label_option(s, pointmap["long_name"].get(s) if s in pointmap.index else None, use_long)
        for s in available
    }

    default_vars: list[str] = []
    if plot_type == "Time series":
        default_vars = output_names[:3] if output_names else input_names[:3]

    with st.sidebar:
        st.markdown("### Variables")
        chosen_labels = st.multiselect(
            "Variables to plot",
            options=[label_map[s] for s in available],
            default=[label_map[s] for s in default_vars if s in label_map],
            key=f"vars_multiselect__{run.key}",
        )
    reverse = {v: k for k, v in label_map.items()}
    chosen_vars = [reverse[c] for c in chosen_labels]

    time_range: Optional[tuple[float, float]] = None
    filtered_windows = windows
    filter_mode = filter_choice[0]
    if filter_mode == "block":
        filtered_windows = [w for w in windows if _block_prefix(w.label) == filter_choice[1]]
    elif filter_mode == "step":
        filtered_windows = [w for w in windows if w.label == filter_choice[1]]
    if filter_mode != "all" and filtered_windows:
        time_range = (filtered_windows[0].t_start, filtered_windows[-1].t_end)

    _render_header(run, script, windows)

    st.plotly_chart(
        build_pass_fail_ribbon(filtered_windows or windows),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    if plot_type == "Time series":
        if not chosen_vars:
            st.info("Pick one or more variables from the sidebar to plot.")
        else:
            fig = build_timeseries(
                run,
                script,
                variables=chosen_vars,
                windows=windows,
                time_range=time_range,
            )
            st.plotly_chart(fig, use_container_width=True)

    elif plot_type == "Deviation heatmap":
        heat_outputs = [v for v in chosen_vars if v in output_names] or output_names
        fig = build_heatmap(run, script, outputs=heat_outputs)
        st.plotly_chart(fig, use_container_width=True)

    elif plot_type == "Step drill-down":
        step_options = [w.label for w in windows]
        if filter_mode == "step":
            default_step_idx = step_options.index(filter_choice[1])
        else:
            first_fail = next((w.label for w in windows if w.passed is False), None)
            default_step_idx = (
                step_options.index(first_fail) if first_fail in step_options
                else min(1, len(step_options) - 1)
            )
        step_choice = st.selectbox("Step", options=step_options, index=default_step_idx)
        detail_outputs = [v for v in chosen_vars if v in output_names] or output_names
        fig = build_step_detail(run, script, step_label=step_choice, outputs=detail_outputs)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Per-step deviation table", expanded=False):
        dev = per_step_deviation(run, script, windows)
        if chosen_vars:
            table_outputs = [v for v in chosen_vars if v in output_names] or output_names
            dev = dev[dev["output"].isin(table_outputs)]
        if filter_mode == "block":
            dev = dev[dev["step_label"].map(_block_prefix) == filter_choice[1]]
        elif filter_mode == "step":
            dev = dev[dev["step_label"] == filter_choice[1]]
        st.dataframe(_styled_deviation(dev), use_container_width=True, hide_index=True)


def _render_header(run: RunHandle, script: TestScript, windows: list) -> None:
    passed = run.overall_passed()
    if passed is True:
        badge = "PASS"
    elif passed is False:
        first_fail = next((w for w in windows if w.passed is False), None)
        badge = f"FAIL at {first_fail.label}" if first_fail else "FAIL"
    else:
        badge = "— status unknown"

    total = run.total_duration_minutes()
    total_str = f"{total:.2f} min" if total is not None else "—"

    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
    c1.metric("Test type", run.test_type)
    c2.metric("Run", run.run_name)
    c3.metric("Steps", len(windows))
    c4.metric("Duration", total_str)
    c5.metric("Result", badge)


def _styled_deviation(df: pd.DataFrame):
    def _row_style(row):
        if row.get("passed") is False:
            return ["background-color: rgba(228, 87, 86, 0.18)"] * len(row)
        if row.get("passed") is True:
            return ["background-color: rgba(84, 162, 75, 0.10)"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1).format(
        {
            "expected": _fmt_val,
            "actual": _fmt_val,
            "tolerance": _fmt_val,
            "deviation": _fmt_val,
            "normalized": _fmt_val,
        }
    )


def _fmt_val(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    import math

    if math.isnan(f):
        return "—"
    return f"{f:.4g}"


main()
