from __future__ import annotations

import unittest

from util.runtime_preflight import (
    collect_import_failures,
    format_import_failures,
    installed_pyodide_modules,
    missing_pyodide_payloads,
)


class RuntimePreflightTests(unittest.TestCase):
    def test_matches_installed_distributions_and_normalizes_names(self):
        lock_packages = {
            "pillow": {"name": "Pillow", "imports": ["PIL"]},
            "scikit-learn": {
                "name": "scikit-learn",
                "imports": ["sklearn"],
            },
            "unused": {"name": "unused", "imports": ["unused"]},
            "metadata-only": {"name": "metadata-only", "imports": []},
        }

        self.assertEqual(
            installed_pyodide_modules(
                ["pillow", "scikit_learn", "metadata.only"], lock_packages
            ),
            {
                "pillow": ("PIL",),
                "scikit-learn": ("sklearn",),
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


if __name__ == "__main__":
    unittest.main()
