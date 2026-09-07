"""Locate test runs and read per-test-type config to find the Excel test
script and the point-map file."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from .run import RunHandle


def find_project_root(start: Optional[Path] = None) -> Path:
    """Walk up from ``start`` looking for a folder that contains
    ``conformance_tests/``. Falls back to the current working directory.

    This is the same rooting convention as the runner: the test folder is
    expected at ``<root>/conformance_tests/<test_type>/``.
    """
    cwd = Path(start or Path.cwd()).resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "conformance_tests").is_dir():
            return candidate
        if (candidate / "tests" / "conformance_tests").is_dir():
            return candidate / "tests"
    return cwd


def list_runs(project_root: Optional[Path] = None) -> list[RunHandle]:
    """Enumerate all runs under ``<root>/conformance_tests/*/results/run_*/``.

    Results are sorted newest-first by folder name (``run_YYYYMMDDTHHMMSS``
    sorts lexicographically the same as chronologically).
    """
    root = Path(project_root) if project_root else find_project_root()
    handles: list[RunHandle] = []
    for values_csv in root.glob("conformance_tests/*/results/run_*/*_values.csv"):
        try:
            handles.append(RunHandle(values_csv.parent))
        except FileNotFoundError:
            continue
    handles.sort(key=lambda h: h.run_name, reverse=True)
    return handles


def load_test_config(project_root: Path, test_type: str) -> dict:
    """Load ``conformance_tests/{test_type}/config/config.yaml``."""
    p = Path(project_root) / "conformance_tests" / test_type / "config" / "config.yaml"
    with open(p) as f:
        return yaml.safe_load(f)


def load_global_config(project_root: Path) -> dict:
    """Load ``{project_root}/config/global_config.yaml`` — the same file the
    runner reads. Empty dict if the file is absent (viz can still run without
    it, using the fallback device_type below)."""
    p = Path(project_root) / "config" / "global_config.yaml"
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def resolved_device_type(project_root: Path) -> str:
    """Return the ``device_type`` set in the global config (``simulation`` or
    ``bacnet``). Falls back to ``simulation`` if the global config is missing
    or omits ``device_type``."""
    return str(load_global_config(project_root).get("device_type", "simulation"))


def resolve_script_and_pointmap(
    project_root: Path,
    test_type: str,
    device_type: Optional[str] = None,
) -> tuple[Path, Path, dict]:
    """Return (excel_path, pointmap_path, test_config_section).

    Point-map location is read from the test's ``config.yaml`` under
    ``device.<device_type>.point_map`` — no naming-convention guessing. The
    device_type defaults to whatever the current global config specifies.
    Paths in the config are resolved relative to ``project_root``.

    ``test_config_section`` is the ``test`` sub-dict (headers + script name),
    passed through so the caller can look up the Excel section headers.
    """
    cfg = load_test_config(project_root, test_type)
    test_section = cfg.get("test", {})
    excel_name = test_section.get("test_script")
    if not excel_name:
        raise ValueError(
            f"conformance_tests/{test_type}/config/config.yaml is missing test.test_script"
        )
    excel_path = Path(project_root) / "conformance_tests" / test_type / "test_scripts" / excel_name

    if device_type is None:
        device_type = resolved_device_type(project_root)

    device_section = cfg.get("device", {}).get(device_type)
    if not device_section:
        available = sorted((cfg.get("device") or {}).keys())
        raise ValueError(
            f"conformance_tests/{test_type}/config/config.yaml has no device.{device_type} section "
            f"(available: {available}). Change device_type in global_config.yaml, or add the section."
        )

    pm = device_section.get("point_map")
    if not pm:
        raise ValueError(
            f"conformance_tests/{test_type}/config/config.yaml is missing "
            f"device.{device_type}.point_map"
        )

    pointmap_path = Path(pm)
    if not pointmap_path.is_absolute():
        pointmap_path = Path(project_root) / pointmap_path
    if not pointmap_path.exists():
        raise FileNotFoundError(
            f"point_map file not found at {pointmap_path} "
            f"(from conformance_tests/{test_type}/config/config.yaml → device.{device_type}.point_map)"
        )

    return excel_path, pointmap_path, test_section
