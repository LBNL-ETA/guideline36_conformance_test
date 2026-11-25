"""Load a single test run's artifacts (values.csv, test_times.csv)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from .script import TestScript


@dataclass
class StepWindow:
    """Time window and pass/fail status for one test step."""

    step_number: int
    label: str
    t_start: float
    t_end: float
    passed: Optional[bool]
    checked: bool


class RunHandle:
    """A pointer to one ``conformance_tests/{type}/results/run_.../`` folder."""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir).resolve()
        self.run_name = self.run_dir.name.removeprefix("run_")
        self.test_type = self.run_dir.parent.parent.name

        values_matches = sorted(self.run_dir.glob("*_values.csv"))
        if not values_matches:
            raise FileNotFoundError(f"No *_values.csv in {self.run_dir}")
        self.values_path = values_matches[0]

        times_matches = sorted(self.run_dir.glob("*_test_times.csv"))
        self.test_times_path: Optional[Path] = times_matches[0] if times_matches else None

    def __repr__(self):
        return f"RunHandle(test_type={self.test_type!r}, run={self.run_name!r})"

    @property
    def key(self) -> str:
        return f"{self.test_type}/{self.run_name}"

    def load_values(self) -> pd.DataFrame:
        """Time-series of inputs+outputs. Preserves duplicate timestamps."""
        return pd.read_csv(self.values_path)

    def load_test_times(self) -> Optional[pd.DataFrame]:
        """
        Load the test step timing table from ``*_test_times.csv``.

        Normalizes legacy ``step`` column headers to ``marker`` so older run
        artifacts remain readable.

        Returns
        -------
        df: pandas df or None
          DataFrame of timing and marker rows, or ``None`` if no
          ``*_test_times.csv`` file exists for the run.

        """
        if not self.test_times_path:
            df = None
        else:
            df = pd.read_csv(self.test_times_path, keep_default_na=False)
            if "marker" not in df.columns and "step" in df.columns:
                df = df.rename(columns={"step": "marker"})

        return df

    def overall_passed(self) -> Optional[bool]:
        """
        Determine overall pass/fail status of the run from ``test_times.csv``.

        Returns
        -------
        passed: bool or None
          ``True`` if completion was logged (``marker=999``) without failures,
          ``False`` if a failure was logged (``marker=-1``), or ``None`` if no
          status can be determined.

        """
        tt = self.load_test_times()
        passed = None
        if tt is not None and not tt.empty:
            markers = set(tt["marker"].astype(int).tolist())
            if -1 in markers:
                passed = False
            elif 999 in markers:
                passed = True

        return passed

    def total_duration_minutes(self) -> Optional[float]:
        """
        Return the total run duration in minutes from ``test_times.csv``.

        Returns
        -------
        duration: float or None
          Total elapsed duration in minutes from the ``marker=999`` summary row
          (falling back to ``marker=-1`` for legacy aborted runs), or ``None``
          if unavailable.

        """
        tt = self.load_test_times()
        duration = None
        if tt is not None and not tt.empty:
            row = tt[tt["marker"].astype(int) == 999]
            if row.empty:
                row = tt[tt["marker"].astype(int) == -1]
            if not row.empty:
                duration = float(row.iloc[0]["duration"])

        return duration

    def step_windows(self, script: TestScript) -> list[StepWindow]:
        """
        Return one ``StepWindow`` per executed or reconstructed test step.

        Prefer ``test_times.csv`` (encodes both timing and pass/fail via the
        special ``-1`` / ``999`` marker rows). If it is missing (older runs),
        fall back to reconstructing boundaries from the Excel ``ClockTime``
        column.

        Step numbering matches the runner: ``marker=k`` in ``test_times.csv``
        corresponds to ``script.step_labels[k-1]``. Step 1 is the
        initialization step; it is not written to ``test_times.csv``, so we
        synthesize it here.

        A ``marker=-1`` row records a step failure. When ``test_block`` /
        ``test_step`` columns are present on that row, they identify the
        failing step directly (along with its ``start_time`` and ``end_time``);
        otherwise, for legacy runs that aborted on first failure, the failing
        step is inferred as the one *after* the last succeeded step.

        First step of each *block* (label-prefix group — A1, B1, C1, …) is
        also treated as a non-checked auto-pass, matching the runner's
        ``if i > 1`` guard applied per-block rather than only once overall.

        Parameters
        ----------
        script: TestScript
          Parsed Excel test script providing step labels and clock times.

        Returns
        -------
        windows: list
          List of ``StepWindow`` instances ordered by step number.

        """
        labels = script.step_labels
        tt = self.load_test_times()

        if tt is not None and not tt.empty:
            tt_real = tt[~tt["marker"].astype(int).isin([-1, 999])].copy()
            tt_real["marker"] = tt_real["marker"].astype(int)
            tt_real = tt_real.sort_values("marker").reset_index(drop=True)

            fail_rows = tt[tt["marker"].astype(int) == -1]
            has_block_step_cols = "test_block" in tt.columns and "test_step" in tt.columns

            windows: list[StepWindow] = []

            start_candidates: list[float] = []
            if not tt_real.empty:
                start_candidates.append(float(tt_real.iloc[0]["start_time"]))
            if has_block_step_cols and not fail_rows.empty:
                for _, fr in fail_rows.iterrows():
                    if _resolve_fail_row_label(fr) is not None:
                        start_candidates.append(float(fr["start_time"]))
            first_real_start = min(start_candidates) if start_candidates else 0.0

            windows.append(
                StepWindow(
                    step_number=1,
                    label=labels[0] if labels else "step1",
                    t_start=0.0,
                    t_end=first_real_start,
                    passed=None,
                    checked=False,
                )
            )

            for _, r in tt_real.iterrows():
                k = int(r["marker"])
                label = labels[k - 1] if k - 1 < len(labels) else f"step{k}"
                windows.append(
                    StepWindow(
                        step_number=k,
                        label=label,
                        t_start=float(r["start_time"]),
                        t_end=float(r["end_time"]),
                        passed=True,
                        checked=True,
                    )
                )

            for _, fr in fail_rows.iterrows():
                fail_end_time = float(fr["end_time"])
                resolved_label = _resolve_fail_row_label(fr) if has_block_step_cols else None

                if resolved_label is not None:
                    fail_label = resolved_label
                    if fail_label in labels:
                        aborted_step = labels.index(fail_label) + 1
                    else:
                        aborted_step = (max(w.step_number for w in windows) + 1) if windows else 2
                    fail_start_time = float(fr["start_time"])
                else:
                    last_passed_step = int(tt_real.iloc[-1]["marker"]) if not tt_real.empty else 1
                    aborted_step = last_passed_step + 1
                    fail_start_time = max(w.t_end for w in windows) if windows else 0.0
                    fail_label = (
                        labels[aborted_step - 1]
                        if 0 <= aborted_step - 1 < len(labels)
                        else f"step{aborted_step}"
                    )

                if not any(w.step_number == aborted_step for w in windows):
                    windows.append(
                        StepWindow(
                            step_number=aborted_step,
                            label=fail_label,
                            t_start=fail_start_time,
                            t_end=fail_end_time,
                            passed=False,
                            checked=True,
                        )
                    )
                else:
                    for w in windows:
                        if w.step_number == aborted_step:
                            w.passed = False

            windows.sort(key=lambda w: w.step_number)
            _mark_block_firsts_auto_pass(windows)
        else:
            windows = self._reconstruct_from_script(script)

        return windows

    def _reconstruct_from_script(self, script: TestScript) -> list[StepWindow]:
        windows: list[StepWindow] = []
        t = 0.0
        for i, label in enumerate(script.step_labels, start=1):
            dt = script.clock_time_seconds(label) or 0.0
            windows.append(
                StepWindow(
                    step_number=i,
                    label=label,
                    t_start=t,
                    t_end=t + dt,
                    passed=None,
                    checked=(i > 1),
                )
            )
            t += dt
        _mark_block_firsts_auto_pass(windows)

        return windows


def _resolve_fail_row_label(row: pd.Series) -> Optional[str]:
    """
    Build the step label from a failure marker row's block and step columns.

    Parameters
    ----------
    row: pandas Series
      A row from ``test_times.csv`` with ``marker == -1``.

    Returns
    -------
    label: str or None
      Step label such as ``'BB2'`` or ``'step2'``, or ``None`` if ``test_step``
      is missing or empty.

    """
    raw_step = row.get("test_step")
    if raw_step is None or pd.isna(raw_step) or str(raw_step).strip() == "":
        label = None
    else:
        try:
            sn_str = str(int(float(raw_step)))
        except (TypeError, ValueError):
            sn_str = str(raw_step).strip()
        raw_block = row.get("test_block")
        blk_str = "" if raw_block is None or pd.isna(raw_block) else str(raw_block).strip()
        label = f"{blk_str}{sn_str}" if blk_str else f"step{sn_str}"

    return label


def _block_prefix(label: str) -> str:
    """The alphabetic prefix of a step label — 'A' for 'A1', 'AA' for 'AA3',
    empty for a fallback label like 'step7'."""
    out = ""
    for ch in label:
        if ch.isalpha():
            out += ch
        else:
            break
    return out


def _mark_block_firsts_auto_pass(windows: list[StepWindow]) -> None:
    """Every time the block prefix changes, mark that window as an unchecked
    auto-pass (passed=True, checked=False). Rationale: the runner's first
    step of each block is a state-setup step whose outputs use ``=ANY``; the
    runner doesn't assert on it, and the user wants those shown as green
    rather than gray "not checked"."""
    prev_prefix: Optional[str] = None
    for w in windows:
        prefix = _block_prefix(w.label)
        if prefix and prefix != prev_prefix:
            w.checked = False
            if w.passed is None or w.passed is True:
                w.passed = True
        prev_prefix = prefix or prev_prefix
