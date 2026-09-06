from __future__ import annotations

import unittest

from util.runtime_preflight import (
    collect_import_failures,
    compatible_pyodide_payloads,
    effective_distribution_versions,
    format_import_failures,
    installed_pyodide_modules,
    missing_pyodide_payloads,
    payloads_for_missing_imports,
    project_requirement_names,
)


class RuntimePreflightTests(unittest.TestCase):
    def test_resolves_duplicate_distribution_names_through_effective_lookup(self):
        resolved = {
            "pytest": "9.1.1",
            "svgwrite": "1.4.3",
        }
        calls: list[str] = []

        def version_resolver(name: str) -> str:
            calls.append(name)
            return resolved[name]

        self.assertEqual(
            effective_distribution_versions(
                ["svgwrite", "pytest", "svgwrite"], version_resolver
            ),
            resolved,
        )
        self.assertCountEqual(calls, ["pytest", "svgwrite"])

    def test_reads_project_and_selected_optional_requirement_names(self):
        pyproject = {
            "project": {
                "dependencies": [
                    "svgwrite",
                    "scikit-learn>=1.5; python_version >= '3.11'",
                ],
                "optional-dependencies": {
                    "development": ["pytest>=9.1.1"],
                    "benchmark": ["pytest-benchmark"],
                    "docs": ["sphinx"],
                },
            }
        }

        self.assertEqual(
            project_requirement_names(
                pyproject, optional_groups=("development", "benchmark")
            ),
            {"pytest", "pytest-benchmark", "scikit-learn", "svgwrite"},
        )

    def test_matches_installed_distributions_and_normalizes_names(self):
        lock_packages = {
            "pillow": {"name": "Pillow", "imports": ["PIL"]},
            "scikit-learn": {
                "name": "scikit-learn",
                "imports": ["sklearn"],
            },
            "matplotlib-inline": {
                "name": "matplotlib-inline",
                "imports": ["matplotlib-inline"],
            },
            "unused": {"name": "unused", "imports": ["unused"]},
            "metadata-only": {"name": "metadata-only", "imports": []},
        }

        self.assertEqual(
            installed_pyodide_modules(
                [
                    "pillow",
                    "scikit_learn",
                    "matplotlib_inline",
                    "metadata.only",
                ],
                lock_packages,
            ),
            {
                "matplotlib-inline": ("matplotlib_inline",),
                "pillow": ("PIL",),
                "scikit-learn": ("sklearn",),
            },
        )

    def test_includes_transitive_lock_dependencies(self):
        lock_packages = {
            "pytest": {
                "name": "pytest",
                "imports": ["_pytest", "pytest"],
                "depends": ["pluggy"],
            },
            "pluggy": {
                "name": "pluggy",
                "imports": ["pluggy"],
                "depends": [],
            },
            "unused": {
                "name": "unused",
                "imports": ["unused"],
                "depends": [],
            },
        }

        self.assertEqual(
            installed_pyodide_modules(["pytest"], lock_packages),
            {
                "pluggy": ("pluggy",),
                "pytest": ("_pytest", "pytest"),
            },
        )

    def test_finds_every_installed_package_with_a_missing_import(self):
        installed_modules = {
            "numpy": ("numpy",),
            "pillow": ("PIL",),
            "scipy": ("scipy", "scipy._lib"),
        }

        self.assertEqual(
            missing_pyodide_payloads(
                installed_modules, lambda name: name in {"numpy", "scipy"}
            ),
            ["pillow", "scipy"],
        )

    def test_loads_compatible_payloads_without_replacing_version_overrides(self):
        lock_packages = {
            "pluggy": {"name": "pluggy", "version": "1.6.0"},
            "pytest": {"name": "pytest", "version": "9.0.2"},
            "svgwrite": {"name": "svgwrite", "version": "1.4.3"},
            "typing-extensions": {
                "name": "typing-extensions",
                "version": "4.15.0",
            },
        }

        self.assertEqual(
            compatible_pyodide_payloads(
                lock_packages,
                lock_packages,
                {
                    "pytest": "9.1.1",
                    "svgwrite": "1.4.3",
                    "typing_extensions": "4.16.0",
                },
            ),
            ["pluggy", "svgwrite"],
        )

    def test_import_sweep_collects_all_failures(self):
        def importer(module_name: str):
            if module_name != "working":
                raise ModuleNotFoundError(f"No module named {module_name!r}")
            return object()

        failures = collect_import_failures(
            ["missing_b", "working", "missing_a"], importer
        )

        self.assertEqual(
            failures,
            {
                "missing_a": "ModuleNotFoundError: No module named 'missing_a'",
                "missing_b": "ModuleNotFoundError: No module named 'missing_b'",
            },
        )
        self.assertEqual(
            format_import_failures(failures),
            "- missing_a: ModuleNotFoundError: No module named 'missing_a'\n"
            "- missing_b: ModuleNotFoundError: No module named 'missing_b'",
        )

    def test_maps_all_missing_imports_to_lock_payloads(self):
        failures = {
            "build123d": "ModuleNotFoundError: No module named 'svgwrite'",
            "pytest": "ModuleNotFoundError: No module named 'pluggy._hooks'",
            "other": "RuntimeError: unrelated",
        }
        lock_packages = {
            "pluggy": {"imports": ["pluggy"]},
            "svgwrite": {"imports": ["svgwrite"]},
            "unused": {"imports": ["unused"]},
            "matplotlib-inline": {"imports": ["matplotlib-inline"]},
        }

        self.assertEqual(
            payloads_for_missing_imports(failures, lock_packages),
            ["pluggy", "svgwrite"],
        )


if __name__ == "__main__":
    unittest.main()
