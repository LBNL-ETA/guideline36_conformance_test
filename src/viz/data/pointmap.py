"""Load the point map CSV that maps long ↔ short variable names.

The point map is a small metadata table with three header lines
(``Description`` / ``Version`` / ``Date``) followed by a real header row
(``Long Name, Variable Name, Type, Unit, Tolerance, ...``) and then a row per
point. Inputs and outputs are typically separated by a blank row.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import pandas as pd


HEADER_ROW_INDEX = 3


def load_pointmap(path: Union[str, Path]) -> pd.DataFrame:
    """Return a DataFrame indexed by short variable name.

    Columns
    -------
    long_name : str
    kind : {"input", "output", "unknown"}
    unit : str | None
    tolerance : float | None
        Per-point tolerance from the point map. NOTE: the runner uses the
        per-step ``acceptable_bounds`` row of the Excel test script for its
        assertion; this column is kept for reference only.
    """
    df = pd.read_csv(path, header=HEADER_ROW_INDEX, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]

    df = df[df["Variable Name"].astype(str).str.strip() != ""]

    kind = df["Type"].str.lower().map(
        lambda s: "input" if "input" in s else ("output" if "output" in s else "unknown")
    )

    def _to_float(v: str):
        v = (v or "").strip()
        if not v:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    out = pd.DataFrame(
        {
            "long_name": df["Long Name"].astype(str).str.strip().values,
            "kind": kind.values,
            "unit": df["Unit"].astype(str).str.strip().replace({"": None}).values,
            "tolerance": [_to_float(v) for v in df["Tolerance"].values],
        },
        index=df["Variable Name"].astype(str).str.strip().values,
    )
    out.index.name = "short_name"
    return out
