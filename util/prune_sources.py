#!/usr/bin/env python3
"""Prune generated OCP bindings to the modules used by B123D Studio."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


# Extracted from build123d 0.11.1 and ocp-tessellate 3.5.0 imports.
REQUIRED_MODULES = frozenset(
    {
        "APIHeaderSection",
        "BOPAlgo",
        "BRep",
        "BRepAdaptor",
        "BRepAlgo",
        "BRepAlgoAPI",
        "BRepBndLib",
        "BRepBuilderAPI",
        "BRepCheck",
        "BRepClass3d",
        "BRepExtrema",
        "BRepFeat",
        "BRepFill",
        "BRepFilletAPI",
        "BRepGProp",
        "BRepIntCurveSurface",
        "BRepLProp",
        "BRepLib",
        "BRepMesh",
        "BRepOffset",
        "BRepOffsetAPI",
        "BRepPrimAPI",
        "BRepProj",
        "BRepTools",
        "BinTools",
        "Bnd",
        "ChFi2d",
        "Extrema",
        "Font",
        "GC",
        "GCPnts",
        "GProp",
        "GccEnt",
        "Geom",
        "Geom2d",
        "Geom2dAPI",
        "Geom2dAdaptor",
        "Geom2dGcc",
        "GeomAPI",
        "GeomAbs",
        "GeomAdaptor",
        "GeomConvert",
        "GeomFill",
        "GeomLib",
        "GeomProjLib",
        "Graphic3d",
        "HLRAlgo",
        "HLRBRep",
        "IFSelect",
        "IGESControl",
        "IntAna2d",
        "Interface",
        "LocOpe",
        "Message",
        "NCollection",
        "Precision",
        "Quantity",
        "RWGltf",
        "RWStl",
        "STEPCAFControl",
        "STEPControl",
        "ShapeAnalysis",
        "ShapeCustom",
        "ShapeFix",
        "ShapeUpgrade",
        "Standard",
        "StdFail",
        "StdPrs",
        "StlAPI",
        "TColStd",
        "TColgp",
        "TCollection",
        "TDF",
        "TDataStd",
        "TDocStd",
        "TopAbs",
        "TopExp",
        "TopLoc",
        "TopTools",
        "TopoDS",
        "XCAFApp",
        "XCAFDoc",
        "XSControl",
        "gce",
        "gp",
        "math",
    }
)

REGISTER_LINE = re.compile(
    r"^(?P<indent>\s*)(?:void\s+)?register_(?P<module>[A-Za-z0-9_]+?)"
    r"(?P<enums>_enums)?\((?:py::module&|m)\);\s*$"
)


def module_for_source(path: Path) -> str:
    module = path.stem
    if module.endswith("_pre"):
        module = module.removesuffix("_pre")
    return re.sub(r"_\d+$", "", module)


def prune(source_dir: Path) -> tuple[int, int]:
    source_dir = source_dir.resolve()
    ocp_cpp = source_dir / "OCP.cpp"
    if not ocp_cpp.is_file():
        raise RuntimeError(f"OCP.cpp not found in {source_dir}")

    required_sources = {
        f"{module}{suffix}.cpp"
        for module in REQUIRED_MODULES
        for suffix in ("", "_pre")
    }
    missing_sources = sorted(
        source_name
        for source_name in required_sources
        if not (source_dir / source_name).is_file()
    )
    if missing_sources:
        raise RuntimeError(
            f"Required OCP sources are missing: {', '.join(missing_sources)}"
        )

    removed = 0
    kept = 0
    for path in source_dir.glob("*.cpp"):
        if path.name == "OCP.cpp":
            continue
        if module_for_source(path) in REQUIRED_MODULES:
            kept += 1
        else:
            path.unlink()
            removed += 1

    original_lines = ocp_cpp.read_text(encoding="utf-8").splitlines(keepends=True)
    patched_lines = []
    registrations_removed = 0
    for line in original_lines:
        match = REGISTER_LINE.match(line)
        if match and match.group("module") not in REQUIRED_MODULES:
            registrations_removed += 1
            continue
        patched_lines.append(line)
    ocp_cpp.write_text("".join(patched_lines), encoding="utf-8")

    remaining_registrations = {
        match.group("module")
        for line in patched_lines
        if (match := REGISTER_LINE.match(line))
    }
    unexpected = sorted(remaining_registrations - REQUIRED_MODULES)
    if unexpected:
        raise RuntimeError(f"Unexpected OCP registrations remain: {', '.join(unexpected)}")

    print(
        "Pruned OCP bindings: "
        f"removed {removed} translation units and {registrations_removed} registration lines; "
        f"kept {kept} translation units for {len(REQUIRED_MODULES)} modules."
    )
    return removed, kept


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    args = parser.parse_args()
    prune(args.source_dir)


if __name__ == "__main__":
    main()
