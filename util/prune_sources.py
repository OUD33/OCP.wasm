#!/usr/bin/env python3
"""Prune generated OCP bindings to the modules used by B123D Studio."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import AbstractSet


# Extracted from build123d 0.11.1 and ocp-tessellate 3.5.0 imports, then
# expanded to include the transitive pybind11 base-class registration closure.
REQUIRED_MODULES = frozenset(
    {
        "APIHeaderSection",
        "Adaptor2d",
        "Adaptor3d",
        "AdvApp2Var",
        "AppBlend",
        "AppCont",
        "Approx",
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
        "CDF",
        "CDM",
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
        "GeomPlate",
        "GeomProjLib",
        "Graphic3d",
        "HLRAlgo",
        "HLRBRep",
        "IFSelect",
        "IGESControl",
        "IGESToBRep",
        "IMeshData",
        "IMeshTools",
        "IntAna2d",
        "IntCurveSurface",
        "IntRes2d",
        "Interface",
        "Intf",
        "LocOpe",
        "Message",
        "NCollection",
        "Precision",
        "Prs3d",
        "Poly",
        "Quantity",
        "RWGltf",
        "RWMesh",
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
        "Transfer",
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
CLASS_TEMPLATE = re.compile(r"py::class_<(?P<template>.+)>\s*\(m,")
TYPE_NAME = re.compile(r"\b[A-Za-z_]\w*\b")


def module_for_source(path: Path) -> str:
    module = path.stem
    if module.endswith("_pre"):
        module = module.removesuffix("_pre")
    return re.sub(r"_\d+$", "", module)


def missing_base_dependencies(
    source_dir: Path, required_modules: AbstractSet[str]
) -> dict[str, set[str]]:
    """Find retained modules whose pybind11 base types live in pruned modules."""
    declarations: list[tuple[str, str]] = []
    class_owners: dict[str, str] = {}

    for path in source_dir.glob("*_pre.cpp"):
        module = module_for_source(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            match = CLASS_TEMPLATE.search(line)
            if not match:
                continue
            template = match.group("template")
            type_names = TYPE_NAME.findall(template)
            if not type_names:
                continue
            class_owners.setdefault(type_names[0], module)
            declarations.append((module, template))

    missing: dict[str, set[str]] = {}
    for module, template in declarations:
        if module not in required_modules:
            continue
        dependencies = {
            owner
            for type_name in TYPE_NAME.findall(template)
            if (owner := class_owners.get(type_name)) is not None
            and owner != module
            and owner not in required_modules
        }
        if dependencies:
            missing.setdefault(module, set()).update(dependencies)
    return missing


def prune(source_dir: Path) -> tuple[int, int]:
    source_dir = source_dir.resolve()
    ocp_cpp = source_dir / "OCP.cpp"
    if not ocp_cpp.is_file():
        raise RuntimeError(f"OCP.cpp not found in {source_dir}")

    missing_dependencies = missing_base_dependencies(source_dir, REQUIRED_MODULES)
    if missing_dependencies:
        details = "; ".join(
            f"{module} -> {', '.join(sorted(dependencies))}"
            for module, dependencies in sorted(missing_dependencies.items())
        )
        raise RuntimeError(
            f"Required OCP modules omit pybind11 base dependencies: {details}"
        )

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
