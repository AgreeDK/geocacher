"""
src/opensak/doctor.py — System diagnostic tool for environment and dependency validation.

Checks Python version, virtual environment status, and required dependencies.
Verifies configuration directory access and suggests fixes for missing components.
"""

from __future__ import annotations

import sys
import importlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

# ── Helpers ──────────────────────────────────────────────────────────────

def load_pyproject() -> dict:
    root = Path(__file__).resolve().parents[3]
    pyproject = root / "pyproject.toml"

    if not pyproject.exists():
        return {}

    if tomllib is None:
        return {}

    with open(pyproject, "rb") as f:
        return tomllib.load(f)


def extract_package_name(dep: str) -> str:
    return dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()


def parse_python_requirement(spec: str) -> tuple[int, ...]:
    spec = spec.replace(">=", "").strip()
    return tuple(int(x) for x in spec.split("."))


# ── Checks ───────────────────────────────────────────────────────────────

def check_python(project: dict):
    spec = project.get("requires-python")

    if not spec:
        return "Python", True, sys.version.split()[0]

    required = parse_python_requirement(spec)

    if sys.version_info >= required:
        return "Python", True, sys.version.split()[0]

    return (
        "Python",
        False,
        f"{sys.version.split()[0]} (requires {spec})",
    )


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
    active = (hasattr(sys, "real_prefix") or sys.base_prefix != sys.prefix)
    return "Virtualenv", active, "active" if active else "not active"


def check_config_dir():
    path = Path.home() / ".opensak"

    try:
        path.mkdir(exist_ok=True)
        return "Config dir", True, str(path)
    except Exception:
        return "Config dir", False, str(path)


# ── Runner ───────────────────────────────────────────────────────────────

CHECKS = [
    check_python,
    check_venv,
    check_dependencies,
    check_config_dir,
]


def run():
    print("\nOpenSAK Doctor\n")

    data = load_pyproject()
    project = data.get("project", {})

    all_ok = True

    for check in CHECKS:
        if check is check_dependencies or check is check_python:
            name, ok, msg = check(project)
        else:
            name, ok, msg = check()

        icon = "✔" if ok else "✖"
        print(f"{icon} {name}: {msg}")

        if not ok:
            all_ok = False

    if all_ok:
        print("\nAll checks passed")
    else:
        print("\nSome checks failed")
        print("\nSuggested fix:")
        print("  pip install -r requirements.txt")