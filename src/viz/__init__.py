"""Interactive visualization for G36 conformance test results.

This package provides a Streamlit + Plotly UI for browsing test runs, viewing
input/output trajectories against expected values with tolerance bands, and
drilling into per-step deviations. It reads only the artifacts the runner
produces (`{name}_values.csv`, `{name}_test_times.csv`) plus the Excel test
script and point map, so it does not touch the runner or its device layer.

Entry points:
  - `viz.launcher.main` — the `g36conftest-viz` console script.
  - `viz.launcher.launch_after_test` — used by `g36conftest`'s CLI when the
    global config sets `viz.enabled: true`.
"""
