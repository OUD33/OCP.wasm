"""Helpers for validating packages in the Pyodide integration runtime."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from packaging.requirements import Requirement


def canonicalize_distribution_name(name: str) -> str:
    """Normalize a distribution name using the PyPA name-matching rules."""
    return re.sub(r"[-_.]+", "-", name).lower()


def normalize_lock_import_name(name: str) -> str:
    """Correct distribution-style separators in Pyodide import metadata."""
    # Most lock entries contain real import names, but some (notably
    # matplotlib-inline in Pyodide 314.0.2) contain the distribution name.
    # Hyphens cannot occur in a Python identifier, so the import uses an
    # underscore instead.
    return name.replace("-", "_")


def project_requirement_names(
    pyproject: Mapping[str, Any],
    optional_groups: Iterable[str] = (),
) -> set[str]:
    """Return declared distribution names from selected project groups."""
    project = pyproject.get("project", {})
    if not isinstance(project, Mapping):
        return set()

    raw_requirements: list[Any] = []
    dependencies = project.get("dependencies", ())
    if isinstance(dependencies, (list, tuple)):
        raw_requirements.extend(dependencies)

    optional = project.get("optional-dependencies", {})
    if isinstance(optional, Mapping):
        for group in optional_groups:
            requirements = optional.get(group, ())
            if isinstance(requirements, (list, tuple)):
                raw_requirements.extend(requirements)

    return {
        Requirement(requirement).name
        for requirement in raw_requirements
        if isinstance(requirement, str) and requirement.strip()
    }


def effective_distribution_versions(
    distribution_names: Iterable[str],
    version_resolver: Callable[[str], str],
) -> dict[str, str]:
    """Resolve one effective version per name despite duplicate metadata."""
    return {
        name: version_resolver(name)
        for name in set(distribution_names)
        if name
    }


def installed_pyodide_modules(
    installed_distributions: Iterable[str],
    lock_packages: Mapping[str, Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    """Return lock package keys/imports for installed roots and dependencies."""
    installed = {
        canonicalize_distribution_name(name)
        for name in installed_distributions
        if name
    }
    packages: dict[str, tuple[str, ...]] = {}
    lock_keys_by_name: dict[str, str] = {}

    for lock_key, metadata in lock_packages.items():
        distribution_name = str(metadata.get("name") or lock_key)
        lock_keys_by_name[canonicalize_distribution_name(lock_key)] = lock_key
        lock_keys_by_name[
            canonicalize_distribution_name(distribution_name)
        ] = lock_key

    pending = [
        lock_key
        for distribution_name in installed
        if (lock_key := lock_keys_by_name.get(distribution_name)) is not None
    ]
    visited: set[str] = set()
    while pending:
        lock_key = pending.pop()
        if lock_key in visited:
            continue
        visited.add(lock_key)
        metadata = lock_packages[lock_key]

        raw_imports = metadata.get("imports", ())
        imports = (
            tuple(
                sorted(
                    {
                        normalize_lock_import_name(name)
                        for name in raw_imports
                        if isinstance(name, str) and name
                    }
                )
            )
            if isinstance(raw_imports, (list, tuple))
            else ()
        )
        if imports:
            packages[lock_key] = imports

        raw_dependencies = metadata.get("depends", ())
        if isinstance(raw_dependencies, (list, tuple)):
            pending.extend(
                dependency_key
                for dependency in raw_dependencies
                if isinstance(dependency, str)
                and (
                    dependency_key := lock_keys_by_name.get(
                        canonicalize_distribution_name(dependency)
                    )
                )
                is not None
            )

    return packages


def compatible_pyodide_payloads(
    required_packages: Iterable[str],
    lock_packages: Mapping[str, Mapping[str, Any]],
    installed_versions: Mapping[str, str],
) -> list[str]:
    """Return required lock payloads that will not replace a version override."""
    normalized_versions = {
        canonicalize_distribution_name(name): version
        for name, version in installed_versions.items()
    }
    payloads: list[str] = []

    for lock_key in required_packages:
        metadata = lock_packages[lock_key]
        distribution_name = str(metadata.get("name") or lock_key)
        installed_version = normalized_versions.get(
            canonicalize_distribution_name(distribution_name)
        )
        lock_version = metadata.get("version")
        if (
            installed_version is not None
            and isinstance(lock_version, str)
            and installed_version != lock_version
        ):
            continue
        payloads.append(lock_key)

    return sorted(set(payloads))


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
