"""Parse the Excel test script.

The runner (`src/g36conftest/Test.py`) does this parsing coupled to a device
class in `init_test_sequence` / `format_excel_df`. The viz needs the same
information — per-step expected outputs, tolerances, step labels, per-step
clock time — but must not depend on a device (viz should work on any host).
So we re-implement the same layout logic here, using only pandas and the
point map to bridge names.

Layout of the Excel workbook (as read with ``index_col=0, header=None``):

- **Inputs block**: rows between the ``input_points_header`` label and the
  ``conditions_header`` label. First column of data (col B in the raw sheet)
  holds the short variable name; second (col C) is unused for inputs; the
  remaining columns are one step each.
- **Conditions block**: rows between ``conditions_header`` and
  ``output_points_header``. Its own three sub-rows carry ``ClockTime``
  (HH:MM:SS → seconds), ``VariableName`` (per-step exit condition, may be
  empty), and ``VariableValue`` (the expression to check against).
- **Outputs block**: rows after ``output_points_header``. Same shape as the
  inputs block; the ``acceptable_bounds`` column (col C) carries the absolute
  tolerance the runner uses in `Test.assert_output`.

Two rows anywhere in the sheet — ``Test Block`` and ``Test Step`` — are
combined column-wise into step labels like ``AA1``, ``AA2``, ``BB1`` (matching
`Test._extract_step_labels`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import pandas as pd


@dataclass
class TestScript:
    """Parsed test script.

    ``inputs`` and ``outputs`` are indexed by step label (``AA1``, ``AA2``, …)
    with a leading ``acceptable_bounds`` row; columns are short variable
    names. ``conditions`` is indexed by step label with columns
    ``ClockTime`` (seconds), ``VariableName``, ``VariableValue``.

    ``step_labels`` is ordered the same as the step columns in the Excel.
    ``tolerances`` is a dict keyed by output short name (extracted from the
    ``acceptable_bounds`` row of ``outputs``).
    """

    step_labels: list[str]
    inputs: pd.DataFrame
    outputs: pd.DataFrame
    conditions: pd.DataFrame
    tolerances: dict[str, float] = field(default_factory=dict)

    def num_steps(self) -> int:
        return len(self.step_labels)

    def expected(self, step_label: str) -> pd.Series:
        return self.outputs.loc[step_label]

    def clock_time_seconds(self, step_label: str) -> Optional[float]:
        v = self.conditions.loc[step_label].get("ClockTime")
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


def load_test_script(
    excel_path: Union[str, Path],
    input_points_header: str = "BACnet Inputs",
    conditions_header: str = "Conditions for Evaluation of Test Step",
    output_points_header: str = "BACnet Expected Outputs",
) -> TestScript:
    """Parse an Excel test script into a :class:`TestScript`.

    Section headers default to the BACnet-style labels but can be overridden
    per-test via the test's ``config.yaml`` (matching the runner).
    """
    df = pd.read_excel(excel_path, index_col=0, header=None)

    step_labels = _extract_step_labels(df)

    inputs = _format_block(df.loc[input_points_header:conditions_header].iloc[1:-1], step_labels)
    conditions = _format_conditions(df.loc[conditions_header:output_points_header].iloc[1:-1], step_labels)
    outputs = _format_block(df.loc[output_points_header:].iloc[1:], step_labels)

    tolerances: dict[str, float] = {}
    if "acceptable_bounds" in outputs.index:
        for col, val in outputs.loc["acceptable_bounds"].items():
            try:
                tolerances[col] = float(val)
            except (TypeError, ValueError):
                continue

    return TestScript(
        step_labels=step_labels,
        inputs=inputs,
        outputs=outputs,
        conditions=conditions,
        tolerances=tolerances,
    )


def _extract_step_labels(df: pd.DataFrame) -> list[str]:
    """Mirror of `Test._extract_step_labels` (Test.py:87)."""
    test_block_vals = None
    test_step_vals = None

    for idx in df.index:
        row = df.loc[idx]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        row_list = row.tolist()
        row_str_list = [str(v) for v in row_list if pd.notna(v)]

        if "Test Block" in row_str_list:
            pos = next(i for i, v in enumerate(row_list) if str(v) == "Test Block")
            test_block_vals = [v for v in row_list[pos + 1:] if pd.notna(v)]

        if "Test Step" in row_str_list:
            pos = next(i for i, v in enumerate(row_list) if str(v) == "Test Step")
            test_step_vals = [v for v in row_list[pos + 1:] if pd.notna(v)]

    if test_block_vals and test_step_vals:
        labels = []
        for b, s in zip(test_block_vals, test_step_vals):
            s_str = str(int(s)) if isinstance(s, float) else str(s)
            labels.append(f"{b}{s_str}")
    elif test_step_vals:
        labels = [f"step{int(s) if isinstance(s, float) else s}" for s in test_step_vals]
    else:
        labels = []

    return labels


def _format_block(df: pd.DataFrame, step_labels: list[str]) -> pd.DataFrame:
    """Format an input/output block into a step-indexed DataFrame.

    Matches `Test.format_excel_df` (Test.py:172) for the non-conditions case,
    but skips the point-property indirection: the second raw column already
    holds the short name, so we use it directly.

    Returns a DataFrame indexed by ``acceptable_bounds`` + step labels, with
    columns = short variable names.
    """
    df_new = df.reset_index().drop([0], axis=1)
    step_cols = _step_col_names(step_labels, len(df_new.columns) - 2)
    df_new.columns = ["variable_name", "acceptable_bounds"] + step_cols

    df_new = df_new[df_new["variable_name"].notna()]
    df_new["variable_name"] = df_new["variable_name"].astype(str).str.strip()

    return df_new.set_index("variable_name").T


def _format_conditions(df: pd.DataFrame, step_labels: list[str]) -> pd.DataFrame:
    """Format the conditions block. Matches `Test.format_excel_df` is_cond_df branch.

    Returns a DataFrame indexed by step label with columns ``ClockTime``
    (seconds), ``VariableName``, ``VariableValue``.
    """
    df_new = df.reset_index().drop([0], axis=1)
    step_cols = _step_col_names(step_labels, len(df_new.columns) - 2)
    df_new.columns = ["variable_name", "acceptable_bounds"] + step_cols

    df_new = df_new[df_new["variable_name"].notna()]
    df_new["variable_name"] = df_new["variable_name"].astype(str).str.strip()

    df_new = df_new.set_index("variable_name").T

    if "ClockTime" in df_new.columns:
        def _to_seconds(v):
            if pd.isna(v):
                return None
            try:
                t = pd.to_datetime(v, format="%H:%M:%S")
                return t.hour * 3600 + t.minute * 60 + t.second
            except (ValueError, TypeError):
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

        df_new["ClockTime"] = df_new["ClockTime"].map(_to_seconds)

    return df_new


def _step_col_names(step_labels: list[str], n_step_cols: int) -> list[str]:
    """Return the column names for the step columns of a block.

    Prefer the parsed step labels (``AA1``, ``AA2``, …) when they match the
    number of step columns; otherwise fall back to ``step0``, ``step1``, …
    (matching `Test.format_excel_df`).
    """
    if step_labels and len(step_labels) == n_step_cols:
        return list(step_labels)
    return [f"step{i}" for i in range(n_step_cols)]
