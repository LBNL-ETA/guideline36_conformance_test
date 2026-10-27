"""``g36conftest-viz`` console-script entry-point.

Both invocations (``g36conftest-viz`` and the post-test hook that
``g36conftest`` fires when ``viz.enabled: true``) end up here. We shell out
to Streamlit's own CLI programmatically so we don't have to spawn a
subprocess; ``streamlit.web.cli.main`` reads ``sys.argv`` like the real
``streamlit`` command would.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional


def _main_py() -> str:
    return str((Path(__file__).parent / "main.py").resolve())


def _run_streamlit(script: str, port: int, address: str, script_args: list[str]) -> int:
    from streamlit.web import cli as stcli

    print(
        f"\n[viz] Serving G36 conformance viz on http://{address}:{port}\n"
        f"[viz] From a Docker host, open http://localhost:{port} in your browser.\n"
        f"[viz] Press Ctrl+C to stop.\n",
        flush=True,
    )

    argv = [
        "streamlit",
        "run",
        script,
        "--server.address",
        address,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    if script_args:
        argv.append("--")
        argv.extend(script_args)

    sys.argv = argv
    return int(stcli.main() or 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="g36conftest-viz",
        description="Launch the interactive G36 conformance-test visualization UI.",
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("G36_VIZ_PORT", "8501")))
    parser.add_argument("--address", default=os.environ.get("G36_VIZ_ADDRESS", "0.0.0.0"))
    parser.add_argument("--run", default=None, help="Path to a run_.../ directory to preselect.")
    parser.add_argument("--project-root", default=None, help="Override the project root.")
    args = parser.parse_args()

    script_args: list[str] = []
    if args.run:
        script_args += ["--run", args.run]
    if args.project_root:
        script_args += ["--project-root", args.project_root]

    return _run_streamlit(_main_py(), port=args.port, address=args.address, script_args=script_args)


def launch_after_test(
    run_dir: Path,
    port: int = 8501,
    address: str = "0.0.0.0",
    project_root: Optional[Path] = None,
) -> int:
    """Invoked by ``g36conftest``'s CLI after a save-csv run completes and
    ``viz.enabled: true``. Blocks — the user Ctrl+C's to exit Streamlit."""
    script_args = ["--run", str(Path(run_dir).resolve())]
    if project_root:
        script_args += ["--project-root", str(Path(project_root).resolve())]
    return _run_streamlit(_main_py(), port=port, address=address, script_args=script_args)


if __name__ == "__main__":
    raise SystemExit(main())
