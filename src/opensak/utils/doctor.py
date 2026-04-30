"""
src/opensak/utils/doctor.py — System diagnostic tool for environment and dependency validation.

Checks Python version, virtual environment status, required dependencies,
config directory access, git availability, and active feature flags.
"""

from __future__ import annotations

import sys
import importlib
import importlib.metadata
import subprocess
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────


def _project_metadata() -> dict:
    # Prefer installed package metadata (works in any install mode)
    try:
        meta = importlib.metadata.metadata("opensak")
        return {
            "requires-python": meta.get("Requires-Python", ""),
            "dependencies": [
                r for r in importlib.metadata.requires("opensak") or []
                if "extra ==" not in r
            ],
        }
    except importlib.metadata.PackageNotFoundError:
        pass

    # Fall back to pyproject.toml for source-only / CI environments
    try:
        import tomllib
        pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            return {
                "requires-python": project.get("requires-python", ""),
                "dependencies": project.get("dependencies", []),
            }
    except Exception:
        pass

    return {}


def extract_package_name(dep: str) -> str:
    for sep in ("[", ">", "<", "=", "!", ";", " "):
        dep = dep.split(sep)[0]
    return dep.strip()


def parse_python_requirement(spec: str) -> tuple[int, ...]:
    spec = spec.replace(">=", "").strip()
    return tuple(int(x) for x in spec.split("."))


# ── Checks ────────────────────────────────────────────────────────────────────


def check_python(project: dict):
    spec = project.get("requires-python", "")
    if not spec:
        return "Python", True, sys.version.split()[0]
    required = parse_python_requirement(spec)
    if sys.version_info >= required:
        return "Python", True, sys.version.split()[0]
    return "Python", False, f"{sys.version.split()[0]} (requires {spec})"


IMPORT_ALIASES: dict[str, str] = {
    "PySide6": "PySide6",
}


def check_dependencies(project: dict):
    deps = project.get("dependencies", [])
    missing = []
    for dep in deps:
        pkg = extract_package_name(dep)
        module_name = IMPORT_ALIASES.get(pkg, pkg)
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return "Dependencies", True, "OK"
    return "Dependencies", False, f"Missing: {', '.join(missing)}"


def check_venv():
    active = hasattr(sys, "real_prefix") or sys.base_prefix != sys.prefix
    return "Virtualenv", active, "active" if active else "not active"


def check_config_dir():
    try:
        from opensak.config import get_app_data_dir
        path = get_app_data_dir()
        path.mkdir(parents=True, exist_ok=True)
        return "Config dir", True, str(path)
    except Exception as e:
        return "Config dir", False, str(e)


def check_git():
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "Git", True, result.stdout.strip()
        return "Git", False, "git exited with error"
    except FileNotFoundError:
        return "Git", False, "not found (required for --version flag)"


def check_feature_flags():
    try:
        from opensak.utils import flags as _flags
        from opensak.utils.flags import _RELEASE_DEFAULTS
        lines = [f"{k}={getattr(_flags, k.replace('-', '_'))}" for k in _RELEASE_DEFAULTS]
        return "Feature flags", True, "  ".join(lines)
    except Exception as e:
        return "Feature flags", False, str(e)


# ── Runner ────────────────────────────────────────────────────────────────────


CHECKS = [
    check_python,
    check_venv,
    check_dependencies,
    check_config_dir,
    check_git,
    check_feature_flags,
]

_TAKES_PROJECT = {check_python, check_dependencies}


def run():
    print("\nOpenSAK Doctor\n")

    project = _project_metadata()
    all_ok = True

    for check in CHECKS:
        if check in _TAKES_PROJECT:
            name, ok, msg = check(project)
        else:
            name, ok, msg = check()

        icon = "✔" if ok else "✖"
        print(f"  {icon} {name}: {msg}")

        if not ok:
            all_ok = False

    if all_ok:
        print("\n  All checks passed.")
    else:
        print("\n  Some checks failed.")
        print("  Suggested fix: pip install -e .[dev]")
