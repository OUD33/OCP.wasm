from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from util.prune_sources import REQUIRED_MODULES, prune


class PruneSourcesTests(unittest.TestCase):
    def test_keeps_both_required_translation_units_and_patches_registration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_dir = Path(temporary_directory)
            for module in REQUIRED_MODULES:
                (source_dir / f"{module}.cpp").touch()
                (source_dir / f"{module}_pre.cpp").touch()
            (source_dir / "AIS.cpp").touch()
            (source_dir / "AIS_pre.cpp").touch()
            (source_dir / "OCP.cpp").write_text(
                "void register_BRep_enums(py::module&);\n"
                "void register_AIS_enums(py::module&);\n"
                "void register_BRep(py::module&);\n"
                "void register_AIS(py::module&);\n"
                "    register_BRep_enums(m);\n"
                "    register_AIS_enums(m);\n"
                "    register_BRep(m);\n"
                "    register_AIS(m);\n",
                encoding="utf-8",
            )

            removed, kept = prune(source_dir)

            self.assertEqual(removed, 2)
            self.assertEqual(kept, len(REQUIRED_MODULES) * 2)
            self.assertTrue((source_dir / "BRep.cpp").exists())
            self.assertTrue((source_dir / "BRep_pre.cpp").exists())
            self.assertFalse((source_dir / "AIS.cpp").exists())
            self.assertFalse((source_dir / "AIS_pre.cpp").exists())
            registrations = (source_dir / "OCP.cpp").read_text(encoding="utf-8")
            self.assertIn("register_BRep", registrations)
            self.assertNotIn("register_AIS", registrations)

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
