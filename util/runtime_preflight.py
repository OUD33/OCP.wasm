"""Helpers for validating packages in the Pyodide integration runtime."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any


def canonicalize_distribution_name(name: str) -> str:
    """Normalize a distribution name using the PyPA name-matching rules."""
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_pyodide_modules(
    installed_distributions: Iterable[str],
    lock_packages: Mapping[str, Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    """Return lock package keys and imports for installed distributions."""
    installed = {
        canonicalize_distribution_name(name)
        for name in installed_distributions
        if name
    }
    packages: dict[str, tuple[str, ...]] = {}

    for lock_key, metadata in lock_packages.items():
        distribution_name = str(metadata.get("name") or lock_key)
        if canonicalize_distribution_name(distribution_name) not in installed:
            continue

        raw_imports = metadata.get("imports", ())
        if not isinstance(raw_imports, (list, tuple)):
            continue
        imports = tuple(
            sorted({name for name in raw_imports if isinstance(name, str) and name})
        )
        if imports:
            packages[lock_key] = imports

    return packages


def missing_pyodide_payloads(
    installed_modules: Mapping[str, tuple[str, ...]],
    module_available: Callable[[str], bool],
) -> list[str]:
    """Find installed Pyodide distributions whose import payload is absent."""
    return sorted(
        package
        for package, imports in installed_modules.items()
        if any(not module_available(module) for module in imports)
    )


def collect_import_failures(
    module_names: Iterable[str],
    importer: Callable[[str], object],
) -> dict[str, str]:
    """Import every module and retain all failures instead of stopping early."""
    failures: dict[str, str] = {}
    for module_name in sorted(set(module_names)):
        try:
            importer(module_name)
        except Exception as exc:  # noqa: BLE001 - aggregation is the purpose here
            failures[module_name] = f"{type(exc).__name__}: {exc}"
    return failures


def format_import_failures(failures: Mapping[str, str]) -> str:
    """Format aggregate failures deterministically for CI logs."""
    return "\n".join(
        f"- {module_name}: {message}"
        for module_name, message in sorted(failures.items())
    )
