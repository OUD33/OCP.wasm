from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from util.prune_sources import (
    REQUIRED_MODULES,
    missing_base_dependencies,
    missing_default_argument_dependencies,
    prune,
)


class PruneSourcesTests(unittest.TestCase):
    def test_inventory_contains_transitive_registration_dependencies(self):
        self.assertEqual(len(REQUIRED_MODULES), 124)
        self.assertIn("math", REQUIRED_MODULES)
        self.assertIn("Adaptor2d", REQUIRED_MODULES)
        self.assertIn("BSplCLib", REQUIRED_MODULES)
        self.assertIn("Convert", REQUIRED_MODULES)
        self.assertIn("SelectBasics", REQUIRED_MODULES)

    def test_detects_a_base_class_owned_by_an_omitted_module(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            (source_dir / "Derived_pre.cpp").write_text(
                'py::class_<Derived_Type, shared_ptr<Derived_Type>, Base_Type >(m,"Derived_Type");\n',
                encoding="utf-8",
            )
            (source_dir / "Base_pre.cpp").write_text(
                'py::class_<Base_Type, shared_ptr<Base_Type> >(m,"Base_Type");\n',
                encoding="utf-8",
            )

            self.assertEqual(
                missing_base_dependencies(source_dir, {"Derived"}),
                {"Derived": {"Base"}},
            )

    def test_detects_a_default_enum_owned_by_an_omitted_module(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            (source_dir / "Geometry.cpp").write_text(
                '.def("convert", &convert, py::arg("mode")='
                "static_cast<const Convert_Mode>(Convert_Default));\n",
                encoding="utf-8",
            )
            (source_dir / "Geometry_pre.cpp").touch()
            (source_dir / "Convert.cpp").touch()
            (source_dir / "Convert_pre.cpp").write_text(
                'py::enum_<Convert_Mode>(m, "Convert_Mode");\n',
                encoding="utf-8",
            )

            self.assertEqual(
                missing_default_argument_dependencies(source_dir, {"Geometry"}),
                {"Geometry": {"Convert"}},
            )

    def test_keeps_both_required_translation_units_and_patches_registration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            for module in REQUIRED_MODULES:
                (source_dir / f"{module}.cpp").touch()
                (source_dir / f"{module}_pre.cpp").touch()
            (source_dir / "Unused.cpp").touch()
            (source_dir / "Unused_pre.cpp").touch()
            (source_dir / "OCP.cpp").write_text(
                "void register_BRep_enums(py::module&);\n"
                "void register_Unused_enums(py::module&);\n"
                "void register_BRep(py::module&);\n"
                "void register_Unused(py::module&);\n"
                "    register_BRep_enums(m);\n"
                "    register_Unused_enums(m);\n"
                "    register_BRep(m);\n"
                "    register_Unused(m);\n",
                encoding="utf-8",
            )

            removed, kept = prune(source_dir)

            self.assertEqual(removed, 2)
            self.assertEqual(kept, len(REQUIRED_MODULES) * 2)
            self.assertTrue((source_dir / "BRep.cpp").exists())
            self.assertTrue((source_dir / "BRep_pre.cpp").exists())
            self.assertFalse((source_dir / "Unused.cpp").exists())
            self.assertFalse((source_dir / "Unused_pre.cpp").exists())
            registrations = (source_dir / "OCP.cpp").read_text(encoding="utf-8")
            self.assertIn("register_BRep", registrations)
            self.assertNotIn("register_Unused", registrations)

            removed_again, kept_again = prune(source_dir)
            self.assertEqual(removed_again, 0)
            self.assertEqual(kept_again, len(REQUIRED_MODULES) * 2)

    def test_fails_if_the_generated_archive_lacks_a_required_module(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            (source_dir / "OCP.cpp").touch()

            with self.assertRaisesRegex(RuntimeError, "Required OCP sources are missing"):
                prune(source_dir)

    def test_fails_if_one_half_of_a_required_module_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            for module in REQUIRED_MODULES:
                (source_dir / f"{module}.cpp").touch()
                (source_dir / f"{module}_pre.cpp").touch()
            missing_module = min(REQUIRED_MODULES)
            (source_dir / f"{missing_module}_pre.cpp").unlink()
            (source_dir / "OCP.cpp").touch()

            with self.assertRaisesRegex(
                RuntimeError, f"{missing_module}_pre[.]cpp"
            ):
                prune(source_dir)


if __name__ == "__main__":
    unittest.main()
