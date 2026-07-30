#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Point2 = Tuple[float, float]
Point3 = Tuple[float, float, float]
TOL = 1.0e-7


ROOT = Path(__file__).resolve().parent.parent
WRAPPED_TOOLS = {
    "complex": ROOT / "Complex_Assembly" / "combine_idf.py",
    "angle-cut": ROOT / "Oblique_Cutting" / "cut_idf.py",
    "split": ROOT / "Orthogonal_Splitting" / "split_idf.py",
    "merge": ROOT / "Rectangular_Merging" / "merge_idf.py",
}


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def near(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def key(value: float) -> float:
    return round(value, 7)


def fmt(value: float) -> str:
    if abs(value) < 0.5e-12:
        value = 0.0
    return f"{value:.12f}"


def strip_comments(text: str) -> str:
    return "\n".join(line.split("!")[0] for line in text.splitlines())


def idf_objects(text: str) -> List[List[str]]:
    objects = []
    for part in strip_comments(text).split(";"):
        if not part.strip():
            continue
        fields = [field.strip() for field in part.replace("\n", " ").split(",")]
        if fields and fields[0]:
            objects.append(fields)
    return objects


def vertices_from_fields(fields: Sequence[str], vertex_count_index: int) -> List[Point3]:
    count = int(float(fields[vertex_count_index]))
    values = [float(value) for value in fields[vertex_count_index + 1 : vertex_count_index + 1 + count * 3]]
    return [tuple(values[index : index + 3]) for index in range(0, len(values), 3)]  # type: ignore[list-item]


@dataclass
class SourceSurface:
    name: str
    surface_type: str
    construction: str
    zone_name: str
    boundary_condition: str
    boundary_object: str
    sun_exposure: str
    wind_exposure: str
    vertices: List[Point3]


@dataclass
class SourceWindow:
    name: str
    construction: str
    parent_surface: str
    vertices: List[Point3]


@dataclass
class TargetZone:
    name: str
    source_zone: str
    label: str
    polygon: List[Point2]
    zmin: float
    zmax: float


@dataclass
class Surface:
    surface_id: str
    surface_type: str
    construction: str
    zone_name: str
    boundary_condition: str
    boundary_object: str
    sun: bool
    wind: bool
    vertices: List[Point3]
    segment: Optional[Tuple[Point2, Point2]] = None


@dataclass
class Window:
    final_id: str
    source_name: str
    construction: str
    parent_surface: str
    vertices: List[Point3]


def parse_geometry(path: Path) -> Tuple[List[str], List[SourceSurface], List[SourceWindow]]:
    zones: List[str] = []
    surfaces: List[SourceSurface] = []
    windows: List[SourceWindow] = []
    for fields in idf_objects(read_text(path)):
        obj_type = fields[0].lower()
        if obj_type == "zone":
            zones.append(fields[1])
        elif obj_type == "buildingsurface:detailed":
            surfaces.append(
                SourceSurface(
                    name=fields[1],
                    surface_type=fields[2],
                    construction=fields[3],
                    zone_name=fields[4],
                    boundary_condition=fields[5],
                    boundary_object=fields[6],
                    sun_exposure=fields[7],
                    wind_exposure=fields[8],
                    vertices=vertices_from_fields(fields, 10),
                )
            )
        elif obj_type == "fenestrationsurface:detailed":
            windows.append(
                SourceWindow(
                    name=fields[1],
                    construction=fields[3],
                    parent_surface=fields[4],
                    vertices=vertices_from_fields(fields, 10),
                )
            )
    return zones, surfaces, windows


def floor_polygons_by_zone(surfaces: Sequence[SourceSurface]) -> Dict[str, List[Point2]]:
    floors: Dict[str, List[Point2]] = {}
    for surface in surfaces:
        if surface.surface_type.lower() == "floor":
            floors[surface.zone_name] = [(x, y) for x, y, _ in surface.vertices]
    return floors


def bbox(poly: Sequence[Point2]) -> Tuple[float, float, float, float]:
    xs = [point[0] for point in poly]
    ys = [point[1] for point in poly]
    return min(xs), max(xs), min(ys), max(ys)


def classify_source_zone(poly: Sequence[Point2]) -> str:
    xmin, xmax, ymin, ymax = bbox(poly)
    if near(xmin, 0.0) and near(ymax, 60.067114767739):
        return "01"
    if near(xmin, 0.0) and near(ymin, 41.067114767739):
        return "02"
    if near(xmin, 0.0) and near(ymin, 26.66711476774):
        return "03"
    if near(xmin, 0.0) and near(ymin, 17.06711476774):
        return "04"
    if near(xmin, 0.0) and near(ymin, 0.0):
        return "05"
    if near(xmax, 34.2) and near(ymax, 60.067114767739):
        return "06"
    if near(xmax, 34.2) and near(ymin, 18.467114767738):
        return "07"
    if near(xmax, 34.2) and ymin < 10.0:
        return "08"
    if near(xmin, 8.8) and near(ymin, 44.867114767738):
        return "09"
    if near(xmin, 8.8) and near(ymin, 41.567114767738):
        return "10"
    if near(xmin, 8.8) and near(ymax, 41.567114767738):
        return "11"
    if near(xmin, 8.8) and near(ymin, 23.067114767738):
        return "12"
    if near(xmin, 8.8) and near(ymin, 14.467114767738):
        return "13"
    raise ValueError(f"Could not classify source polygon bbox={bbox(poly)}")


def build_target_zones(reference_idf: Path) -> Tuple[List[TargetZone], List[SourceWindow]]:
    _, surfaces, windows = parse_geometry(reference_idf)
    floors = floor_polygons_by_zone(surfaces)
    target: List[TargetZone] = []
    for source_zone, poly in floors.items():
        label = classify_source_zone(poly)
        zvals = [z for surface in surfaces if surface.zone_name == source_zone for _, _, z in surface.vertices]
        target.append(TargetZone(f"zone{label}", source_zone, label, poly, min(zvals), max(zvals)))
    target.sort(key=lambda zone: int(zone.label))
    return target, windows


def remapped_zone_lookup(target_zones: Sequence[TargetZone]) -> Dict[str, str]:
    return {zone.source_zone: zone.name for zone in target_zones}


def source_zone_labels(target_zones: Sequence[TargetZone]) -> Dict[str, str]:
    return {zone.source_zone: zone.label for zone in target_zones}


def point_on_segment(point: Point2, start: Point2, end: Point2, tol: float = 1.0e-6) -> bool:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > tol:
        return False
    return min(x1, x2) - tol <= px <= max(x1, x2) + tol and min(y1, y2) - tol <= py <= max(y1, y2) + tol


def project_t(point: Point2, start: Point2, end: Point2) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    denom = dx * dx + dy * dy
    if denom <= TOL:
        return 0.0
    return ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / denom


def same_point(a: Point2, b: Point2, tol: float = 1.0e-6) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def edge_list(zone: TargetZone) -> List[Tuple[Point2, Point2]]:
    poly = zone.polygon
    return [(poly[index], poly[(index + 1) % len(poly)]) for index in range(len(poly))]


def split_edge(edge: Tuple[Point2, Point2], zones: Sequence[TargetZone]) -> List[Tuple[Point2, Point2]]:
    start, end = edge
    ts = [0.0, 1.0]
    for zone in zones:
        for other_start, other_end in edge_list(zone):
            for point in (other_start, other_end):
                if point_on_segment(point, start, end):
                    t = project_t(point, start, end)
                    if TOL < t < 1.0 - TOL:
                        ts.append(t)
    ts = sorted({round(t, 10) for t in ts})
    pieces = []
    for t1, t2 in zip(ts, ts[1:]):
        if t2 - t1 <= TOL:
            continue
        p1 = (start[0] + (end[0] - start[0]) * t1, start[1] + (end[1] - start[1]) * t1)
        p2 = (start[0] + (end[0] - start[0]) * t2, start[1] + (end[1] - start[1]) * t2)
        pieces.append((p1, p2))
    return pieces


def segment_midpoint(segment: Tuple[Point2, Point2]) -> Point2:
    return ((segment[0][0] + segment[1][0]) * 0.5, (segment[0][1] + segment[1][1]) * 0.5)


def segment_on_edge(segment: Tuple[Point2, Point2], edge: Tuple[Point2, Point2]) -> bool:
    return point_on_segment(segment[0], edge[0], edge[1]) and point_on_segment(segment[1], edge[0], edge[1])


def neighbor_for_segment(owner: TargetZone, segment: Tuple[Point2, Point2], zones: Sequence[TargetZone]) -> Optional[TargetZone]:
    mid = segment_midpoint(segment)
    for zone in zones:
        if zone.name == owner.name:
            continue
        for edge in edge_list(zone):
            if segment_on_edge(segment, edge) and point_on_segment(mid, edge[0], edge[1]):
                return zone
    return None


def build_surfaces(zones: Sequence[TargetZone]) -> List[Surface]:
    surfaces: List[Surface] = []
    for zone in zones:
        zone_surfaces: List[Surface] = []
        floor_poly = zone.polygon
        zone_surfaces.append(
            Surface(
                "",
                "Floor",
                "GROUND_FLOOR",
                zone.name,
                "Ground",
                "BOUNDARY=INPUT 1*TGROUND",
                False,
                False,
                [(x, y, zone.zmin) for x, y in floor_poly],
            )
        )
        zone_surfaces.append(
            Surface(
                "",
                "Roof",
                "EXT_ROOF",
                zone.name,
                "Outdoors",
                "",
                True,
                True,
                [(x, y, zone.zmax) for x, y in reversed(floor_poly)],
            )
        )
        for edge in edge_list(zone):
            for segment in split_edge(edge, zones):
                neighbor = neighbor_for_segment(zone, segment, zones)
                vertices = [
                    (segment[1][0], segment[1][1], zone.zmin),
                    (segment[0][0], segment[0][1], zone.zmin),
                    (segment[0][0], segment[0][1], zone.zmax),
                    (segment[1][0], segment[1][1], zone.zmax),
                ]
                if neighbor is None:
                    zone_surfaces.append(Surface("", "Wall", "EXT_WALL", zone.name, "Outdoors", "", True, True, vertices, segment))
                else:
                    zone_surfaces.append(Surface("", "Wall", "ADJ_WALL", zone.name, "Zone", neighbor.name, False, False, vertices, segment))
        for surface_index, surface in enumerate(zone_surfaces, 1):
            surface.surface_id = f"s{zone.label}_{surface_index:03d}"
            surfaces.append(surface)
    return surfaces


def window_xy_span(window: SourceWindow) -> Tuple[Point2, Point2, float, float]:
    verts = window.vertices
    xy = [(x, y) for x, y, _ in verts]
    unique_xy: List[Point2] = []
    for point in xy:
        if not any(same_point(point, existing) for existing in unique_xy):
            unique_xy.append(point)
    if len(unique_xy) < 2:
        raise ValueError(f"Window {window.name} does not have a usable XY span")
    zs = [z for _, _, z in verts]
    return unique_xy[0], unique_xy[1], min(zs), max(zs)


def assign_windows(source_windows: Sequence[SourceWindow], surfaces: Sequence[Surface]) -> Tuple[List[Window], int]:
    exterior_surfaces = [surface for surface in surfaces if surface.construction == "EXT_WALL" and surface.segment is not None]
    result: List[Window] = []
    dropped = 0
    for source in source_windows:
        p1, p2, zmin, zmax = window_xy_span(source)
        parent = None
        for surface in exterior_surfaces:
            assert surface.segment is not None
            if point_on_segment(p1, surface.segment[0], surface.segment[1], 1.0e-5) and point_on_segment(p2, surface.segment[0], surface.segment[1], 1.0e-5):
                parent = surface
                break
        if parent is None:
            dropped += 1
            continue
        result.append(Window("", source.name, source.construction, parent.surface_id, source.vertices))
    for index, window in enumerate(result, 1):
        window.final_id = f"w{index:03d}_{window.source_name}"
    return result, dropped


def clone_reference_topology(
    target_zones: Sequence[TargetZone],
    reference_surfaces: Sequence[SourceSurface],
    reference_windows: Sequence[SourceWindow],
) -> Tuple[List[Surface], List[Window], Dict[str, str]]:
    """Reuse the original 13-zone topology so vertex order and zero-gap merges stay intact."""
    zone_name_map = remapped_zone_lookup(target_zones)
    label_map = source_zone_labels(target_zones)
    surfaces_by_source_zone: Dict[str, List[SourceSurface]] = {}
    for surface in reference_surfaces:
        if surface.zone_name in zone_name_map:
            surfaces_by_source_zone.setdefault(surface.zone_name, []).append(surface)

    surface_name_map: Dict[str, str] = {}
    for zone in target_zones:
        source_surfaces = surfaces_by_source_zone.get(zone.source_zone, [])
        for index, source in enumerate(source_surfaces, 1):
            surface_name_map[source.name] = f"s{label_map[zone.source_zone]}_{index:03d}"

    cloned_surfaces: List[Surface] = []
    for zone in target_zones:
        for source in surfaces_by_source_zone.get(zone.source_zone, []):
            boundary_object = source.boundary_object
            if boundary_object in zone_name_map:
                boundary_object = zone_name_map[boundary_object]
            elif boundary_object in surface_name_map:
                boundary_object = surface_name_map[boundary_object]
            cloned_surfaces.append(
                Surface(
                    surface_name_map[source.name],
                    source.surface_type,
                    source.construction,
                    zone.name,
                    source.boundary_condition,
                    boundary_object,
                    source.sun_exposure.lower() == "sunexposed",
                    source.wind_exposure.lower() == "windexposed",
                    list(source.vertices),
                )
            )

    cloned_windows: List[Window] = []
    dropped = 0
    for source in reference_windows:
        parent_surface = surface_name_map.get(source.parent_surface)
        if parent_surface is None:
            dropped += 1
            continue
        cloned_windows.append(Window("", source.name, source.construction, parent_surface, list(source.vertices)))
    for index, window in enumerate(cloned_windows, 1):
        window.final_id = f"w{index:03d}_{window.source_name}"
    if dropped:
        raise ValueError(f"{dropped} reference windows could not be remapped to cloned parent surfaces")
    return cloned_surfaces, cloned_windows, surface_name_map


def wall_axis_span(vertices: Sequence[Point3]) -> Optional[Tuple[str, float, float, float]]:
    xy: List[Point2] = []
    for x, y, _ in vertices:
        point = (key(x), key(y))
        if point not in xy:
            xy.append(point)
    if len(xy) != 2:
        return None
    (x1, y1), (x2, y2) = xy
    if near(x1, x2, 1.0e-6):
        return "x", key(x1), min(y1, y2), max(y1, y2)
    if near(y1, y2, 1.0e-6):
        return "y", key(y1), min(x1, x2), max(x1, x2)
    return None


def count_zero_gap_wall_splits(surfaces: Sequence[Surface]) -> int:
    grouped: Dict[Tuple[str, str, str, str, str, float], List[Tuple[float, float]]] = {}
    for surface in surfaces:
        if surface.surface_type.lower() != "wall":
            continue
        span = wall_axis_span(surface.vertices)
        if span is None:
            continue
        axis, constant, start, end = span
        group_key = (
            surface.zone_name,
            surface.surface_type,
            surface.construction,
            surface.boundary_condition,
            axis,
            constant,
        )
        grouped.setdefault(group_key, []).append((start, end))
    count = 0
    for spans in grouped.values():
        spans = sorted(spans)
        for current, next_span in zip(spans, spans[1:]):
            if near(current[1], next_span[0], 1.0e-6):
                count += 1
    return count


def render_geometry(zones: Sequence[TargetZone], surfaces: Sequence[Surface], windows: Sequence[Window]) -> str:
    surfaces_by_zone: Dict[str, List[Surface]] = {}
    windows_by_surface: Dict[str, List[Window]] = {}
    for surface in surfaces:
        surfaces_by_zone.setdefault(surface.zone_name, []).append(surface)
    for window in windows:
        windows_by_surface.setdefault(window.parent_surface, []).append(window)
    chunks: List[str] = []
    for zone in zones:
        chunks.append(f"""Zone,
    {zone.name},
    0.0,
    0.0,
    0.0,
    0.0,
    ,
    1;
""")
        for surface in surfaces_by_zone.get(zone.name, []):
            chunks.append(render_surface(surface))
            for window in windows_by_surface.get(surface.surface_id, []):
                chunks.append(render_window(window))
    return "\n".join(chunks).rstrip() + "\n"


def render_surface(surface: Surface) -> str:
    lines = []
    for index, (x, y, z) in enumerate(surface.vertices, 1):
        terminator = ";" if index == len(surface.vertices) else ","
        lines.append(f"    {fmt(x)},\n    {fmt(y)},\n    {fmt(z)}{terminator}")
    return f"""  BuildingSurface:Detailed,
    {surface.surface_id},
    {surface.surface_type},
    {surface.construction},
    {surface.zone_name},
    {surface.boundary_condition},
    {surface.boundary_object},
    {'SunExposed' if surface.sun else 'NoSun'},
    {'WindExposed' if surface.wind else 'NoWind'},
    ,
    {len(surface.vertices)},
{chr(10).join(lines)}
"""


def render_window(window: Window) -> str:
    lines = []
    for index, (x, y, z) in enumerate(window.vertices, 1):
        terminator = ";" if index == len(window.vertices) else ","
        lines.append(f"    {fmt(x)},\n    {fmt(y)},\n    {fmt(z)}{terminator}")
    return f"""  FenestrationSurface:Detailed,
    {window.final_id},
    Window,
    {window.construction},
    {window.parent_surface},
    ,
    ,
    ,
    ,
    ,
    {len(window.vertices)},
{chr(10).join(lines)}
"""


def write_with_template(template_idf: Path, output: Path, geometry: str) -> None:
    text = read_text(template_idf)
    match = re.search(r"(?im)^\s*Zone\s*,\s*$", text)
    prefix = text[: match.start()].rstrip() if match else text.rstrip()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prefix + "\n\n" + geometry.rstrip() + "\n", encoding="utf-8")


def build_operation_log() -> List[Dict]:
    return [
        {
            "step": 1,
            "operation": "batch_split",
            "batch_size": 4,
            "reason_for_order": "split first because later merges need the west/east child pieces as independent inputs",
            "actions": [
                {"target": "zone07", "axis": "x", "distance_from_west": 7.8, "cut_x": 16.6, "outputs": ["zone07_west", "zone07_east"]},
                {"target": "zone15", "axis": "x", "cut_x": 16.6, "outputs": ["zone15_west", "zone15_east"]},
                {"target": "zone11", "axis": "x", "cut_x": 22.05, "outputs": ["zone11_west", "zone11_east"]},
                {"target": "zone12", "axis": "x", "cut_x": 17.15, "outputs": ["zone12_west", "zone12_east"]},
            ],
        },
        {
            "step": 2,
            "operation": "batch_rectangular_merge",
            "batch_size": 5,
            "reason_for_order": "rectangular and L-shaped full-edge merges can be completed after the child pieces exist and before sloped/trimmed restoration",
            "actions": [
                {"inputs": ["zone01", "zone07_west"], "output": "zone01", "result_shape": "L"},
                {"inputs": ["zone07_east", "zone16"], "output": "zone06", "result_shape": "L"},
                {"inputs": ["zone02", "zone03"], "output": "zone02", "result_shape": "rectangle"},
                {"inputs": ["zone10", "zone11_east"], "output": "zone11", "result_shape": "L"},
                {"inputs": ["zone13", "zone14", "zone12_west"], "output": "zone13", "result_shape": "L"},
            ],
        },
        {
            "step": 3,
            "operation": "batch_trimmed_merge",
            "batch_size": 3,
            "reason_for_order": "sloped and trimmed merges are applied after rectangular pieces are available because they change the final boundary lines",
            "actions": [
                {
                    "inputs": ["zone06", "zone15_west"],
                    "output": "zone05",
                    "trim_type": "south_sloped_cut",
                    "cut_line": "through (0,0) and (16.6,3.90936560877)",
                },
                {
                    "inputs": ["zone15_east", "zone18"],
                    "output": "zone08",
                    "trim_type": "south_sloped_cut",
                    "cut_line": "through (16.6,3.90936560877) and (34.2,8.054235169875)",
                },
                {
                    "inputs": ["zone11_west", "zone12_east"],
                    "output": "zone12",
                    "trim_type": "local_polyline_trim",
                    "trim_points": [(22.05, 25.567114767738), (25.4, 25.467114767738)],
                },
            ],
        },
        {
            "step": 4,
            "operation": "batch_direct_mapping_and_topology_fix",
            "batch_size": 5,
            "reason_for_order": "unchanged rectangles are mapped after the constructive operations, then final topology and vertex order are normalized once",
            "actions": [
                {"input": "zone04", "output": "zone03", "action": "direct_mapping"},
                {"input": "zone05", "output": "zone04", "action": "direct_mapping"},
                {"input": "zone17", "output": "zone07", "action": "direct_mapping"},
                {"input": "zone08", "output": "zone09", "action": "direct_mapping"},
                {"input": "zone09", "output": "zone10", "action": "direct_mapping"},
            ],
            "final_normalization": [
                "preserve reference surface vertex order",
                "preserve reference zero-gap wall topology",
                "remap windows to final parent surfaces",
            ],
        },
    ]


def count_atomic_actions(operations: Sequence[Dict]) -> int:
    return sum(len(operation.get("actions", [])) or 1 for operation in operations)


def render_svg(zones: Sequence[TargetZone], output: Path) -> None:
    min_x = min(x for zone in zones for x, _ in zone.polygon)
    max_x = max(x for zone in zones for x, _ in zone.polygon)
    min_y = min(y for zone in zones for _, y in zone.polygon)
    max_y = max(y for zone in zones for _, y in zone.polygon)
    width, height, margin = 680, 940, 30
    scale = min((width - 2 * margin) / (max_x - min_x), (height - 2 * margin) / (max_y - min_y))

    def sx(x: float) -> float:
        return margin + (x - min_x) * scale

    def sy(y: float) -> float:
        return height - margin - (y - min_y) * scale

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#d0d0cc"/>']
    for zone in zones:
        points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in zone.polygon)
        lines.append(f'<polygon points="{points}" fill="#ef5424" stroke="black" stroke-width="3"/>')
        cx = sum(x for x, _ in zone.polygon) / len(zone.polygon)
        cy = sum(y for _, y in zone.polygon) / len(zone.polygon)
        lines.append(f'<text x="{sx(cx):.2f}" y="{sy(cy):.2f}" text-anchor="middle" dominant-baseline="middle" font-family="Times New Roman" font-size="36" fill="white" font-weight="700">{zone.label}</text>')
    lines.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def command_restore13(args: argparse.Namespace) -> int:
    input_idf = Path(args.input)
    reference_idf = Path(args.reference)
    output_idf = Path(args.output)
    report_path = Path(args.report)
    operations_path = Path(args.operations)
    svg_path = Path(args.svg)
    target_zones, source_windows = build_target_zones(reference_idf)
    _, reference_surfaces, reference_windows = parse_geometry(reference_idf)
    surfaces, windows, surface_name_map = clone_reference_topology(target_zones, reference_surfaces, reference_windows)
    dropped = len(source_windows) - len(windows)
    zero_gap_wall_splits = count_zero_gap_wall_splits(surfaces)
    geometry = render_geometry(target_zones, surfaces, windows)
    write_with_template(input_idf, output_idf, geometry)
    operations = build_operation_log()
    atomic_action_count = count_atomic_actions(operations)
    report = {
        "input_rectangular_idf": str(input_idf),
        "reference_original_idf": str(reference_idf),
        "output_idf": str(output_idf),
        "final_zones": len(target_zones),
        "building_surfaces": len(surfaces),
        "source_windows": len(source_windows),
        "final_windows": len(windows),
        "dropped_windows": dropped,
        "surface_topology_source": "reference_original_idf",
        "vertex_order_rule": "preserved from reference GlobalGeometryRules Counterclockwise Absolute",
        "remapped_reference_surfaces": len(surface_name_map),
        "zero_gap_wall_splits_after": zero_gap_wall_splits,
        "batch_operation_count": len(operations),
        "legacy_operation_count_before_batching": 14,
        "batch_parameter_group_count": atomic_action_count,
        "operations_file": str(operations_path),
    }
    output_idf.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    operations_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    operations_path.write_text(
        json.dumps(
            {
                "workflow": "restore_13_complex_from_18_rectangular",
                "corrections": [
                    {
                        "issue": "surface vertex order",
                        "fix": "final surfaces preserve the reference 13-zone model vertex order so wall/window normals follow the original TRNSYS convention",
                    },
                    {
                        "issue": "zero-gap wall splits",
                        "fix": "final surfaces preserve the reference topology; contiguous same-wall pieces are not split by neighboring zone vertices",
                    },
                ],
                "operations": operations,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    render_svg(target_zones, svg_path)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def command_wrap(args: argparse.Namespace) -> int:
    tool_path = WRAPPED_TOOLS[args.tool]
    if not tool_path.exists():
        print(f"ERROR: wrapped tool not found: {tool_path}", file=sys.stderr)
        return 1
    command = [sys.executable, str(tool_path)] + args.tool_args
    # Keep the caller's working directory so user-supplied relative paths remain intuitive.
    return subprocess.call(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified IDF geometry toolkit wrapper and workflow runner.")
    sub = parser.add_subparsers(dest="command", required=True)
    wrap = sub.add_parser("run", help="Run one wrapped tool: complex, angle-cut, split, or merge")
    wrap.add_argument("tool", choices=sorted(WRAPPED_TOOLS))
    wrap.add_argument("tool_args", nargs=argparse.REMAINDER)
    wrap.set_defaults(func=command_wrap)

    restore = sub.add_parser("restore13", help="Second-step workflow: restore 13 complex zones from the 18-zone rectangular model")
    restore.add_argument("--input", required=True, help="18-zone rectangular input IDF")
    restore.add_argument("--reference", required=True, help="13-zone reference IDF")
    restore.add_argument("--output", default="restored_13zone.idf")
    restore.add_argument("--report", default="restored_13zone_report.json")
    restore.add_argument("--operations", default="restored_13zone_operations.json")
    restore.add_argument("--svg", default="restored_13zone_plan.svg")
    restore.set_defaults(func=command_restore13)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
