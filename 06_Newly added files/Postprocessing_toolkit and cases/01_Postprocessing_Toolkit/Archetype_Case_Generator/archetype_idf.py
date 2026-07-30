#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Complex_Assembly"))

import combine_idf as core  # noqa: E402


ShapeName = str

SHAPES = ("L", "T", "U", "H", "Cross", "CourtyardAtrium")
PICK_NAMES = ("start", "middle", "end")

GRID_MASKS: Dict[str, List[Tuple[int, int]]] = {
    "L": [(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)],
    "T": [(0, 2), (1, 2), (2, 2), (1, 1), (1, 0)],
    "U": [(0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2), (1, 0)],
    "H": [(0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2), (1, 1)],
    "Cross": [(1, 0), (1, 1), (1, 2), (0, 1), (2, 1)],
    "CourtyardAtrium": [
        (0, 0),
        (1, 0),
        (2, 0),
        (0, 1),
        (2, 1),
        (0, 2),
        (1, 2),
        (2, 2),
    ],
}


class Component:
    def __init__(self, source: Path, role: str, orientation: str) -> None:
        self.role = role
        self.orientation = orientation
        self.cells = core.load_instance(source, role, orientation)

    @property
    def floors(self) -> List[List[core.Cell]]:
        return core._floor_groups(self.cells, core._role_axis(self.orientation))

    @property
    def min_cells_per_floor(self) -> int:
        return min(len(floor) for floor in self.floors)


def pick(floor: Sequence[core.Cell], which: str) -> core.Cell:
    if which == "start":
        return floor[0]
    if which == "middle":
        return floor[len(floor) // 2]
    if which == "end":
        return floor[-1]
    raise ValueError(f"Unknown pick position: {which}")


def merge_each_floor(
    left: Component,
    left_pick: str,
    right: Component,
    right_pick: str,
) -> List[Tuple[str, str]]:
    if len(left.floors) != len(right.floors):
        raise ValueError(f"{left.role} and {right.role} have different floor counts")
    return [
        (pick(left_floor, left_pick).uid, pick(right_floor, right_pick).uid)
        for left_floor, right_floor in zip(left.floors, right.floors)
    ]


def place(
    target: Component,
    target_pick: str,
    moving: Component,
    moving_pick: str,
    side: str,
) -> None:
    target_cell = pick(target.floors[0], target_pick)
    moving_cell = pick(moving.floors[0], moving_pick)
    core.place_branch_for_t(target_cell, moving_cell, moving.cells, side)


def all_cells(components: Iterable[Component]) -> List[core.Cell]:
    cells: List[core.Cell] = []
    for component in components:
        cells.extend(component.cells)
    return cells


def build_bar_model(source: Path, shape: ShapeName) -> Tuple[List[core.Cell], List[Tuple[str, str]], str]:
    if shape == "L":
        main = Component(source, "main", "ew")
        leg = Component(source, "leg", "ns")
        place(main, "start", leg, "start", "north")
        merges = merge_each_floor(main, "start", leg, "start")
        operation = "main=ew, leg=ns; place leg:start north of main:start; merge main:start=leg:start on each floor"
        return all_cells([main, leg]), merges, operation

    if shape == "T":
        stem = Component(source, "stem", "ns")
        cap = Component(source, "cap", "ew")
        place(stem, "end", cap, "middle", "north")
        merges = merge_each_floor(stem, "end", cap, "middle")
        operation = "stem=ns, cap=ew; place cap:middle north of stem:end; merge stem:end=cap:middle on each floor"
        return all_cells([stem, cap]), merges, operation

    if shape == "U":
        bottom = Component(source, "bottom", "ew")
        left = Component(source, "left", "ns")
        right = Component(source, "right", "ns")
        place(bottom, "start", left, "start", "north")
        place(bottom, "end", right, "start", "north")
        merges = []
        merges.extend(merge_each_floor(bottom, "start", left, "start"))
        merges.extend(merge_each_floor(bottom, "end", right, "start"))
        operation = (
            "bottom=ew, left/right=ns; place left:start north of bottom:start and "
            "right:start north of bottom:end; merge both lower corners on each floor"
        )
        return all_cells([bottom, left, right]), merges, operation

    if shape == "H":
        left = Component(source, "left", "ns")
        connector = Component(source, "connector", "ew")
        right = Component(source, "right", "ns")
        place(left, "middle", connector, "start", "east")
        place(connector, "end", right, "middle", "east")
        merges = []
        merges.extend(merge_each_floor(left, "middle", connector, "start"))
        merges.extend(merge_each_floor(connector, "end", right, "middle"))
        operation = (
            "left/right=ns, connector=ew; place connector:start east of left:middle "
            "and right:middle east of connector:end; merge both connector ends on each floor"
        )
        return all_cells([left, connector, right]), merges, operation

    if shape == "Cross":
        stem = Component(source, "stem", "ns")
        west_arm = Component(source, "west_arm", "ew")
        east_arm = Component(source, "east_arm", "ew")
        place(stem, "middle", west_arm, "end", "west")
        place(stem, "middle", east_arm, "start", "east")
        merges = []
        merges.extend(merge_each_floor(stem, "middle", west_arm, "end"))
        merges.extend(merge_each_floor(stem, "middle", east_arm, "start"))
        operation = (
            "stem=ns, west/east arms=ew; place west_arm:end west of stem:middle "
            "and east_arm:start east of stem:middle; merge both arms to the center on each floor"
        )
        return all_cells([stem, west_arm, east_arm]), merges, operation

    if shape == "CourtyardAtrium":
        south = Component(source, "south", "ew")
        west = Component(source, "west", "ns")
        east = Component(source, "east", "ns")
        north = Component(source, "north", "ew")
        place(south, "start", west, "start", "north")
        place(south, "end", east, "start", "north")
        place(west, "end", north, "start", "north")
        merges = []
        merges.extend(merge_each_floor(south, "start", west, "start"))
        merges.extend(merge_each_floor(south, "end", east, "start"))
        merges.extend(merge_each_floor(west, "end", north, "start"))
        merges.extend(merge_each_floor(east, "end", north, "end"))
        operation = (
            "south/north=ew, west/east=ns; place west/east legs north of south corners, "
            "then place north:start north of west:end; merge all four ring corners on each floor"
        )
        return all_cells([south, west, east, north]), merges, operation

    raise ValueError(f"Unsupported shape: {shape}")


def should_use_grid_fallback(source: Path) -> bool:
    sample = Component(source, "sample", "ew")
    return sample.min_cells_per_floor < 3


def component_extent(cells: Sequence[core.Cell]) -> Tuple[float, float]:
    xmin = min(cell.xmin for cell in cells)
    xmax = max(cell.xmax for cell in cells)
    ymin = min(cell.ymin for cell in cells)
    ymax = max(cell.ymax for cell in cells)
    return xmax - xmin, ymax - ymin


def build_grid_model(source: Path, shape: ShapeName, reason: str) -> Tuple[List[core.Cell], List[Tuple[str, str]], str]:
    mask = GRID_MASKS[shape]
    probe = core.load_instance(source, "probe", "ew")
    width, depth = component_extent(probe)

    cells: List[core.Cell] = []
    for index, (grid_x, grid_y) in enumerate(mask, 1):
        role = f"grid{index:02d}"
        component_cells = core.load_instance(source, role, "ew")
        core.translate_cells(component_cells, grid_x * width, grid_y * depth)
        cells.extend(component_cells)

    operation = (
        f"component-grid assembly ({reason}); shape mask={mask}; component orientation=ew; "
        f"cell spacing=({width:.6f}, {depth:.6f}); no zone merges"
    )
    return cells, [], operation


def build_model(source: Path, shape: ShapeName, force_grid: bool) -> Tuple[List[core.Cell], List[Tuple[str, str]], str, str]:
    if force_grid:
        cells, merges, operation = build_grid_model(source, shape, "forced to keep identical component orientation and remove rotated non-square joint offsets")
        return cells, merges, operation, "component_grid"
    if should_use_grid_fallback(source):
        cells, merges, operation = build_grid_model(source, shape, "one-cell-per-floor source")
        return cells, merges, operation, "component_grid"
    cells, merges, operation = build_bar_model(source, shape)
    return cells, merges, operation, "bar_assembly"


def default_template_for_source(source: Path) -> Path:
    candidate = source.parent / "Empty_Zone_Template_01_06.idf"
    if candidate.exists():
        return candidate
    return core.default_template_for_source(source)


def generate(args: argparse.Namespace) -> Dict[str, object]:
    source = Path(args.source)
    template = Path(args.template) if args.template else default_template_for_source(source)
    output = Path(args.output)

    cells, merges, operation, mode = build_model(source, args.shape, args.force_grid)
    cells_by_uid = {cell.uid: cell for cell in cells}
    final_zones = core.assign_final_zones(cells, merges)
    surfaces = core.build_surfaces(final_zones, cells)
    windows, dropped_windows = core.assign_windows(final_zones, surfaces)
    errors = core.validate_model(final_zones, cells, merges, cells_by_uid, surfaces, windows)
    if errors:
        raise ValueError("; ".join(errors))

    geometry = core.render_idf_geometry(final_zones, surfaces, windows)
    core.write_with_template(template, output, geometry)

    report: Dict[str, object] = {
        "shape": args.shape,
        "generation_mode": mode,
        "tool": "Archetype_Case_Generator/archetype_idf.py",
        "geometry_core": "Complex_Assembly/combine_idf.py",
        "source": str(source),
        "template": str(template),
        "output": str(output),
        "operation": operation,
        "input_cells": len(cells),
        "merge_pairs": len(merges),
        "final_zones": len(final_zones),
        "building_surfaces": len(surfaces),
        "fenestration_surfaces": len(windows),
        "dropped_windows": dropped_windows,
        "merges": [{"left": left, "right": right} for left, right in merges],
    }
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate L/T/U/H/Cross/Courtyard-Atrium IDF archetypes from a base rectangular-zone task.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--shape", choices=SHAPES, required=True)
    parser.add_argument("--source", required=True, help="Base ex*.py source containing compressed zones")
    parser.add_argument("--template", help="Base IDF template")
    parser.add_argument("--output", required=True, help="Output IDF path")
    parser.add_argument("--report", help="Optional JSON report path")
    parser.add_argument("--force-grid", action="store_true", help="Use component-grid layout even when bar assembly is possible")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        report = generate(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
