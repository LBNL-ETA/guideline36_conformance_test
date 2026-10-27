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
        if not self.test_times_path:
            return None
        return pd.read_csv(self.test_times_path)

    def overall_passed(self) -> Optional[bool]:
        """Return True if the runner logged completion (step=999); False if it
        logged an abort (step=-1); None if no test_times.csv is available."""
        tt = self.load_test_times()
        if tt is None or tt.empty:
            return None
        steps = set(tt["step"].astype(int).tolist())
        if -1 in steps:
            return False
        if 999 in steps:
            return True
        return None

    def total_duration_minutes(self) -> Optional[float]:
        tt = self.load_test_times()
        if tt is None or tt.empty:
            return None
        row = tt[tt["step"].astype(int) == 999]
        if row.empty:
            row = tt[tt["step"].astype(int) == -1]
        if row.empty:
            return None
        return float(row.iloc[0]["duration"])

    def step_windows(self, script: TestScript) -> list[StepWindow]:
        """Return one :class:`StepWindow` per test step.

        Prefer ``test_times.csv`` (encodes both timing and pass/fail via the
        special ``-1`` / ``999`` rows). If it's missing (older runs), fall
        back to reconstructing boundaries from the Excel ``ClockTime`` column.

        Step numbering matches the runner: ``step=k`` in ``test_times.csv``
        corresponds to ``script.step_labels[k-1]`` (see Test.py:285 —
        ``self.step_labels[i-1]``). Step 1 is the initialization step; it is
        not written to ``test_times.csv``, so we synthesize it here.

        The ``step=-1`` row is a *marker* meaning "test aborted", not a step
        number. The actual failing step is the one *after* the last row that
        succeeded — its label comes from ``step_labels`` at that position.

        First step of each *block* (label-prefix group — A1, B1, C1, …) is
        also treated as a non-checked auto-pass, matching the runner's
        ``if i > 1`` guard applied per-block rather than only once overall.
        """
        labels = script.step_labels
        tt = self.load_test_times()

        if tt is not None and not tt.empty:
            tt_real = tt[~tt["step"].astype(int).isin([-1, 999])].copy()
            tt_real["step"] = tt_real["step"].astype(int)
            tt_real = tt_real.sort_values("step").reset_index(drop=True)

            fail_row = tt[tt["step"].astype(int) == -1]
            fail_end_time = float(fail_row.iloc[0]["end_time"]) if not fail_row.empty else None

            windows: list[StepWindow] = []

            first_real_start = float(tt_real.iloc[0]["start_time"]) if not tt_real.empty else 0.0
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
                k = int(r["step"])
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

            if fail_end_time is not None:
                last_passed_step = int(tt_real.iloc[-1]["step"]) if not tt_real.empty else 1
                aborted_step = last_passed_step + 1
                prev_end = max(w.t_end for w in windows) if windows else 0.0
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
                            t_start=prev_end,
                            t_end=fail_end_time,
                            passed=False,
                            checked=True,
                        )
                    )
                else:
                    for w in windows:
                        if w.step_number == aborted_step:
                            w.passed = False

            _mark_block_firsts_auto_pass(windows)
            return windows

        return self._reconstruct_from_script(script)

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
