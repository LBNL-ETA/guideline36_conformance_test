"""Per-step deviation of actual vs expected output values.

Mirrors the runner's assertion in `Test.assert_output` (Test.py:559): the
tolerance is treated as an absolute error bound, and the special ``ANY`` /
``LAST`` / expression forms in the expected column are recognised. Values
originating from Excel expressions (``=…``, ``INTERPOLATE(...)``, ``LAST``)
are not evaluated here — they are flagged in the ``note`` column and reported
as ``expected = None`` so plots can indicate "not directly comparable" for
those cells.

Boundary-row precision: ``test_times.csv`` stores step end-times with ``%f``
(6-decimal) precision, but the runner writes CSV rows at times that differ
by ~1e-7s across the step boundary — so a strict ``time <= t_end`` filter
misses the "Conditions met" row (the one the runner actually asserted on).
We compensate with a 1-microsecond precision slop that lets that row in;
in exchange, at step boundaries the "actual" may include one row of the
next step's initial transient. Users can inspect the full trajectory in
the time-series view to disambiguate.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from ..data.run import RunHandle, StepWindow
from ..data.script import TestScript


def per_step_deviation(
    run: RunHandle,
    script: TestScript,
    windows: Optional[list[StepWindow]] = None,
) -> pd.DataFrame:
    """Return a long-form DataFrame with one row per (step, output).

    Columns: ``step_number``, ``step_label``, ``output``, ``expected``,
    ``actual``, ``tolerance``, ``deviation``, ``normalized`` (=|dev|/tol),
    ``passed``, ``note``.
    """
    values = run.load_values()
    windows = windows or run.step_windows(script)

    output_names = [c for c in script.outputs.columns if c in values.columns]

    rows = []
    for w in windows:
        actuals = _actual_at_end(values, w.t_end)

        if w.label in script.outputs.index:
            expected_row = script.outputs.loc[w.label]
        else:
            expected_row = pd.Series({name: np.nan for name in output_names})

        for name in output_names:
            expected_raw = expected_row.get(name)
            tol = float(script.tolerances.get(name, math.nan))
            actual = actuals.get(name, math.nan)

            expected: Optional[float]
            note = ""
            passed: Optional[bool] = None

            if not w.checked:
                expected = _try_float(expected_raw)
                note = "not checked (init step)"
            elif isinstance(expected_raw, str):
                s = expected_raw.strip()
                if "ANY" in s:
                    expected = None
                    passed = True
                    note = "expected = ANY"
                elif "LAST" in s or s.startswith("="):
                    expected = None
                    note = "expression (see test script)"
                else:
                    expected = _try_float(s)
                    passed = _compare(actual, expected, tol)
            else:
                expected = _try_float(expected_raw)
                passed = _compare(actual, expected, tol)

            deviation: Optional[float]
            normalized: Optional[float]
            if expected is None or actual is None or _isnan(actual) or _isnan(expected):
                deviation = None
                normalized = None
            else:
                deviation = float(actual) - float(expected)
                if tol and not _isnan(tol) and tol > 0:
                    normalized = abs(deviation) / tol
                else:
                    normalized = None if not deviation else float("inf")

            rows.append(
                {
                    "step_number": w.step_number,
                    "step_label": w.label,
                    "output": name,
                    "expected": expected,
                    "actual": actual,
                    "tolerance": tol if not _isnan(tol) else None,
                    "deviation": deviation,
                    "normalized": normalized,
                    "passed": passed,
                    "note": note,
                }
            )

    return pd.DataFrame(rows)


def _actual_at_end(values: pd.DataFrame, t_end: float) -> dict[str, float]:
    """Return the runner's "conditions met" row for this step.

    At each step boundary the runner writes up to three CSV rows in quick
    succession (~1e-7s apart): (A) the last ``test_conditions`` loop-tail
    print, (B) ``start_test``'s "Conditions met" print — this is the one
    ``assert_output`` operates on — and (C) the *next* step's first
    ``test_conditions`` print, which set_values has already dirtied with
    the next step's inputs.

    ``test_times.csv`` stores ``t_end`` with ``%f`` (6-decimal) precision so
    it lands somewhere in this triplet after rounding; we accept up to 1e-6s
    of slop to include all three rows, then walk back from the end of the
    filtered set to identify the boundary group (rows within 1s of each
    other) and pick row B: the second-to-last of a 3-row group, the last of
    a 2-row group (the final step has no C row), or the sole row otherwise.
    """
    if values.empty or "time" not in values.columns:
        return {}
    subset = values[values["time"] <= t_end + 1e-6]
    if subset.empty:
        subset = values.iloc[[0]]
    row = subset.iloc[_canonical_row_index(subset)]
    return {c: row[c] for c in values.columns if c != "time"}


def _canonical_row_index(subset: pd.DataFrame, boundary_gap_s: float = 1.0) -> int:
    """Pick the "conditions met" row within ``subset``. See :func:`_actual_at_end`
    for the reasoning; ``boundary_gap_s`` is the time-gap threshold that
    separates the boundary group from the preceding intra-step samples
    (which sit 10s apart)."""
    n = len(subset)
    if n <= 1:
        return 0

    boundary_start = n - 1
    times = subset["time"].values
    for i in range(n - 2, -1, -1):
        if times[i + 1] - times[i] > boundary_gap_s:
            break
        boundary_start = i

    group_size = n - boundary_start
    if group_size >= 3:
        return n - 2
    return n - 1


def _try_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def _compare(actual, expected, tolerance) -> Optional[bool]:
    """Match `Test.assert_output`: |expected − actual| > tolerance ⇒ fail."""
    a = _try_float(actual)
    e = _try_float(expected)
    t = _try_float(tolerance)
    if a is None or e is None:
        return None
    if t is None:
        t = 0.0
    return abs(e - a) <= t


def _isnan(v) -> bool:
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False
