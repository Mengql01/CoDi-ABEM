#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Point3 = Tuple[float, float, float]
Rect2 = Tuple[float, float, float, float]

TOL = 1.0e-7


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text()


def near(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def key(value: float) -> float:
    return round(value, 7)


def fmt(value: float) -> str:
    if abs(value) < 0.5e-12:
        value = 0.0
    return f"{value:.12f}"


def interval_overlap(a1: float, a2: float, b1: float, b2: float) -> float:
    return min(a2, b2) - max(a1, b1)


def positive_overlap(a1: float, a2: float, b1: float, b2: float) -> bool:
    return interval_overlap(a1, a2, b1, b2) > TOL


def inside_open(value: float, low: float, high: float) -> bool:
    return low + TOL < value < high - TOL


def inside_closed(value: float, low: float, high: float) -> bool:
    return low - TOL <= value <= high + TOL


def rect_contains_point(rect: Rect2, x: float, y: float) -> bool:
    return inside_open(x, rect[0], rect[1]) and inside_open(y, rect[2], rect[3])


@dataclass
class Window:
    source_id: str
    construction: str
    parent_source_id: str
    original_vertices: List[Point3]
    side: str
    axis_min: float
    axis_max: float
    zmin: float
    zmax: float
    plane: str
    constant: float
    vertices: List[Point3] = field(default_factory=list)
    final_id: str = ""
    parent_surface: str = ""
    source_zone: str = ""


@dataclass
class OriginalZone:
    name: str
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    windows: List[Window] = field(default_factory=list)

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def depth(self) -> float:
        return self.ymax - self.ymin

    @property
    def footprint_key(self) -> Tuple[float, float, float, float]:
        return (key(self.xmin), key(self.xmax), key(self.ymin), key(self.ymax))


@dataclass
class Cell:
    name: str
    source_zone: str
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    windows: List[Window] = field(default_factory=list)

    @property
    def rect(self) -> Rect2:
        return (self.xmin, self.xmax, self.ymin, self.ymax)

    @property
    def cx(self) -> float:
        return 0.5 * (self.xmin + self.xmax)

    @property
    def cy(self) -> float:
        return 0.5 * (self.ymin + self.ymax)

    @property
    def cz(self) -> float:
        return 0.5 * (self.zmin + self.zmax)


@dataclass
class Surface:
    surface_id: str
    surface_type: str
    construction: str
    zone_name: str
    boundary_cond: str
    boundary_obj: str
    sun: bool
    wind: bool
    vertices: List[Point3]
    plane: Optional[str] = None
    constant: Optional[float] = None
    span_a: Optional[Tuple[float, float]] = None
    span_z: Optional[Tuple[float, float]] = None
    side: str = ""
    internal_split_wall: bool = False


def extract_zones_from_python(path: Path) -> List[Tuple]:
    text = read_text(path)
    tree = ast.parse(text, filename=str(path))
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "zones":
                    values.append(node.value)
    if not values:
        raise ValueError(f"No literal variable named 'zones' was found in {path}")
    zones = ast.literal_eval(values[-1])
    if not isinstance(zones, list):
        raise ValueError(f"The 'zones' variable in {path} is not a list")
    return zones


def detect_window_geometry(vertices: Sequence[Point3], zone: OriginalZone) -> Tuple[str, str, float, float, float, float, float]:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    zmin, zmax = min(zs), max(zs)
    if max(ys) - min(ys) <= 1.0e-5:
        y = sum(ys) / len(ys)
        side = "south" if near(y, zone.ymin, 1.0e-5) else "north" if near(y, zone.ymax, 1.0e-5) else "unknown"
        return side, "y", y, min(xs), max(xs), zmin, zmax
    if max(xs) - min(xs) <= 1.0e-5:
        x = sum(xs) / len(xs)
        side = "west" if near(x, zone.xmin, 1.0e-5) else "east" if near(x, zone.xmax, 1.0e-5) else "unknown"
        return side, "x", x, min(ys), max(ys), zmin, zmax
    return "unknown", "unknown", 0.0, 0.0, 0.0, zmin, zmax


def parse_window(def_item: str, zone: OriginalZone) -> Optional[Window]:
    parts = [part.strip() for part in def_item.split(",", 3)]
    if len(parts) < 4 or parts[1] != "EXT_WINDOW1":
        return None
    vertices = [
        tuple(float(piece) for piece in match.strip("()").split(","))  # type: ignore[misc]
        for match in re.findall(r"\([^)]+\)", parts[3])
    ]
    side, plane, constant, axis_min, axis_max, zmin, zmax = detect_window_geometry(vertices, zone)
    return Window(
        source_id=parts[0],
        construction=parts[1],
        parent_source_id=parts[2],
        original_vertices=vertices,  # type: ignore[arg-type]
        side=side,
        axis_min=axis_min,
        axis_max=axis_max,
        zmin=zmin,
        zmax=zmax,
        plane=plane,
        constant=constant,
        source_zone=zone.name,
    )


def load_zones(source: Path) -> List[OriginalZone]:
    zones: List[OriginalZone] = []
    raw_zone_tuples = extract_zones_from_python(source)
    for zone_tuple in raw_zone_tuples:
        name = str(zone_tuple[0])
        vertices = [tuple(map(float, point)) for point in zone_tuple[1]]
        xs = [p[0] for p in vertices]
        ys = [p[1] for p in vertices]
        zs = [p[2] for p in vertices]
        zone = OriginalZone(
            name=name,
            xmin=min(xs),
            xmax=max(xs),
            ymin=min(ys),
            ymax=max(ys),
            zmin=min(zs),
            zmax=max(zs),
        )
        for def_item in zone_tuple[2:]:
            if isinstance(def_item, str):
                window = parse_window(def_item, zone)
                if window is not None:
                    zone.windows.append(window)
        zones.append(zone)
    return zones


def zone_number(name: str) -> Optional[int]:
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else None


def resolve_zone_ref(ref: str, zones: Sequence[OriginalZone]) -> str:
    names = {zone.name for zone in zones}
    if ref in names:
        return ref
    numeric = int(ref) if ref.isdigit() else zone_number(ref)
    if numeric is not None:
        matches = [zone.name for zone in zones if zone_number(zone.name) == numeric]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"Zone reference {ref!r} is ambiguous: {matches}")
    raise ValueError(f"Could not resolve zone reference {ref!r}. Available zones: {sorted(names)}")


def normalize_axis(axis: str) -> str:
    value = axis.strip().lower()
    if value in ("x", "ew", "east-west", "west", "from-west"):
        return "x"
    if value in ("y", "ns", "north-south", "south", "from-south"):
        return "y"
    raise ValueError(f"Unknown split axis {axis!r}; use x/ew or y/ns")


def parse_split_specs(specs: Sequence[str], zones: Sequence[OriginalZone], sync_vertical: bool) -> Dict[str, Dict[str, List[float]]]:
    zone_by_name = {zone.name: zone for zone in zones}
    split_map: Dict[str, Dict[str, List[float]]] = {}
    for spec in specs:
        parts = [part.strip() for part in spec.split(":")]
        if len(parts) != 3:
            raise ValueError(f"Split spec must look like zone03:x:3,6 or zone03:y:2.5, got {spec!r}")
        target_name = resolve_zone_ref(parts[0], zones)
        axis = normalize_axis(parts[1])
        distances = [float(item.strip()) for item in parts[2].split(",") if item.strip()]
        if not distances:
            raise ValueError(f"Split spec {spec!r} does not contain any distance")

        target_zone = zone_by_name[target_name]
        target_names = [target_name]
        if sync_vertical:
            target_names = [
                zone.name
                for zone in zones
                if zone.footprint_key == target_zone.footprint_key
            ]
        for name in target_names:
            split_map.setdefault(name, {"x": [], "y": []})[axis].extend(distances)
    return split_map


def cleaned_distances(distances: Iterable[float], limit: float, zone_name: str, axis: str) -> List[float]:
    cleaned = sorted({key(distance) for distance in distances})
    for distance in cleaned:
        if distance <= TOL or distance >= limit - TOL:
            raise ValueError(f"Invalid {axis}-distance {distance:g} for {zone_name}; it must be inside 0..{limit:g}")
    return cleaned


def split_zones(zones: Sequence[OriginalZone], split_map: Dict[str, Dict[str, List[float]]]) -> List[Cell]:
    cells: List[Cell] = []
    for zone in zones:
        zone_splits = split_map.get(zone.name, {"x": [], "y": []})
        x_distances = cleaned_distances(zone_splits.get("x", []), zone.width, zone.name, "x")
        y_distances = cleaned_distances(zone_splits.get("y", []), zone.depth, zone.name, "y")
        x_coords = [zone.xmin] + [zone.xmin + distance for distance in x_distances] + [zone.xmax]
        y_coords = [zone.ymin] + [zone.ymin + distance for distance in y_distances] + [zone.ymax]
        piece_count = (len(x_coords) - 1) * (len(y_coords) - 1)
        piece_index = 1
        for row in range(len(y_coords) - 1):
            for col in range(len(x_coords) - 1):
                name = zone.name if piece_count == 1 else f"{zone.name}_{piece_index:02d}"
                cell = Cell(
                    name=name,
                    source_zone=zone.name,
                    xmin=x_coords[col],
                    xmax=x_coords[col + 1],
                    ymin=y_coords[row],
                    ymax=y_coords[row + 1],
                    zmin=zone.zmin,
                    zmax=zone.zmax,
                )
                cell.windows = clipped_windows_for_cell(zone, cell)
                cells.append(cell)
                piece_index += 1
    return cells


def clipped_windows_for_cell(zone: OriginalZone, cell: Cell) -> List[Window]:
    windows: List[Window] = []
    for window in zone.windows:
        clipped = clip_window_to_cell(window, zone, cell)
        if clipped is not None:
            windows.append(clipped)
    return windows


def clip_window_to_cell(window: Window, zone: OriginalZone, cell: Cell) -> Optional[Window]:
    if window.side == "south" and near(cell.ymin, zone.ymin):
        a1, a2 = max(window.axis_min, cell.xmin), min(window.axis_max, cell.xmax)
        if a2 - a1 > TOL:
            return make_window_piece(window, cell, "south", a1, a2)
    elif window.side == "north" and near(cell.ymax, zone.ymax):
        a1, a2 = max(window.axis_min, cell.xmin), min(window.axis_max, cell.xmax)
        if a2 - a1 > TOL:
            return make_window_piece(window, cell, "north", a1, a2)
    elif window.side == "west" and near(cell.xmin, zone.xmin):
        a1, a2 = max(window.axis_min, cell.ymin), min(window.axis_max, cell.ymax)
        if a2 - a1 > TOL:
            return make_window_piece(window, cell, "west", a1, a2)
    elif window.side == "east" and near(cell.xmax, zone.xmax):
        a1, a2 = max(window.axis_min, cell.ymin), min(window.axis_max, cell.ymax)
        if a2 - a1 > TOL:
            return make_window_piece(window, cell, "east", a1, a2)
    return None


def make_window_piece(window: Window, cell: Cell, side: str, a1: float, a2: float) -> Window:
    z1, z2 = window.zmin, window.zmax
    if side == "south":
        y = cell.ymin
        vertices = [(a1, y, z2), (a1, y, z1), (a2, y, z1), (a2, y, z2)]
        plane, constant = "y", y
    elif side == "north":
        y = cell.ymax
        vertices = [(a1, y, z1), (a1, y, z2), (a2, y, z2), (a2, y, z1)]
        plane, constant = "y", y
    elif side == "west":
        x = cell.xmin
        vertices = [(x, a2, z1), (x, a1, z1), (x, a1, z2), (x, a2, z2)]
        plane, constant = "x", x
    elif side == "east":
        x = cell.xmax
        vertices = [(x, a2, z2), (x, a1, z2), (x, a1, z1), (x, a2, z1)]
        plane, constant = "x", x
    else:
        raise ValueError(f"Unknown window side: {side}")
    return Window(
        source_id=window.source_id,
        construction=window.construction,
        parent_source_id=window.parent_source_id,
        original_vertices=window.original_vertices,
        side=side,
        axis_min=a1,
        axis_max=a2,
        zmin=z1,
        zmax=z2,
        plane=plane,
        constant=constant,
        vertices=vertices,
        source_zone=window.source_zone,
    )


def horizontal_neighbor(cell: Cell, all_cells: Sequence[Cell], top: bool) -> Optional[Cell]:
    z = cell.zmax if top else cell.zmin
    for other in all_cells:
        if other.name == cell.name:
            continue
        plane_match = near(other.zmin, z) if top else near(other.zmax, z)
        if not plane_match:
            continue
        if rect_contains_point(other.rect, cell.cx, cell.cy):
            return other
    return None


def vertical_neighbor(cell: Cell, side: str, a_mid: float, z_mid: float, all_cells: Sequence[Cell]) -> Optional[Cell]:
    for other in all_cells:
        if other.name == cell.name:
            continue
        if not inside_open(z_mid, other.zmin, other.zmax):
            continue
        if side == "east" and near(other.xmin, cell.xmax) and inside_open(a_mid, other.ymin, other.ymax):
            return other
        if side == "west" and near(other.xmax, cell.xmin) and inside_open(a_mid, other.ymin, other.ymax):
            return other
        if side == "north" and near(other.ymin, cell.ymax) and inside_open(a_mid, other.xmin, other.xmax):
            return other
        if side == "south" and near(other.ymax, cell.ymin) and inside_open(a_mid, other.xmin, other.xmax):
            return other
    return None


def side_breaks(cell: Cell, side: str, all_cells: Sequence[Cell]) -> List[float]:
    if side in ("east", "west"):
        a1, a2 = cell.ymin, cell.ymax
    else:
        a1, a2 = cell.xmin, cell.xmax
    breaks = [a1, a2]
    for other in all_cells:
        if other.name == cell.name:
            continue
        if not positive_overlap(cell.zmin, cell.zmax, other.zmin, other.zmax):
            continue
        if side == "east" and not near(other.xmin, cell.xmax):
            continue
        if side == "west" and not near(other.xmax, cell.xmin):
            continue
        if side == "north" and not near(other.ymin, cell.ymax):
            continue
        if side == "south" and not near(other.ymax, cell.ymin):
            continue
        if side in ("east", "west"):
            if positive_overlap(a1, a2, other.ymin, other.ymax):
                breaks.extend([max(a1, other.ymin), min(a2, other.ymax)])
        else:
            if positive_overlap(a1, a2, other.xmin, other.xmax):
                breaks.extend([max(a1, other.xmin), min(a2, other.xmax)])
    return sorted({key(value) for value in breaks})


def wall_vertices(cell: Cell, side: str, a1: float, a2: float) -> Tuple[List[Point3], str, float, Tuple[float, float]]:
    z1, z2 = cell.zmin, cell.zmax
    if side == "east":
        x = cell.xmax
        return [(x, a2, z2), (x, a1, z2), (x, a1, z1), (x, a2, z1)], "x", x, (a1, a2)
    if side == "west":
        x = cell.xmin
        return [(x, a2, z1), (x, a1, z1), (x, a1, z2), (x, a2, z2)], "x", x, (a1, a2)
    if side == "north":
        y = cell.ymax
        return [(a2, y, z1), (a1, y, z1), (a1, y, z2), (a2, y, z2)], "y", y, (a1, a2)
    if side == "south":
        y = cell.ymin
        return [(a1, y, z1), (a2, y, z1), (a2, y, z2), (a1, y, z2)], "y", y, (a1, a2)
    raise ValueError(f"Unknown side: {side}")


def make_horizontal_surface(cell: Cell, top: bool, neighbor: Optional[Cell], global_ground: float) -> Surface:
    if top:
        vertices = [(cell.xmax, cell.ymin, cell.zmax), (cell.xmax, cell.ymax, cell.zmax), (cell.xmin, cell.ymax, cell.zmax), (cell.xmin, cell.ymin, cell.zmax)]
        if neighbor is not None:
            return Surface("", "Ceiling", "ADJ_CEILING", cell.name, "Zone", neighbor.name, False, False, vertices)
        return Surface("", "Roof", "EXT_ROOF", cell.name, "Outdoors", "", True, True, vertices)

    vertices = [(cell.xmin, cell.ymin, cell.zmin), (cell.xmin, cell.ymax, cell.zmin), (cell.xmax, cell.ymax, cell.zmin), (cell.xmax, cell.ymin, cell.zmin)]
    if neighbor is not None:
        return Surface("", "Floor", "ADJ_CEILING", cell.name, "Zone", neighbor.name, False, False, vertices)
    if near(cell.zmin, global_ground):
        return Surface("", "Floor", "GROUND_FLOOR", cell.name, "Ground", "BOUNDARY=INPUT 1*TGROUND", False, False, vertices)
    return Surface("", "Floor", "EXT_FLOOR", cell.name, "Outdoors", "", True, True, vertices)


def build_surfaces(cells: Sequence[Cell]) -> List[Surface]:
    surfaces: List[Surface] = []
    global_ground = min(cell.zmin for cell in cells)
    ordered = sorted(cells, key=lambda c: (c.zmin, c.xmin, c.ymin, c.name))
    for zone_index, cell in enumerate(ordered, 1):
        zone_surfaces: List[Surface] = [
            make_horizontal_surface(cell, top=False, neighbor=horizontal_neighbor(cell, cells, top=False), global_ground=global_ground),
            make_horizontal_surface(cell, top=True, neighbor=horizontal_neighbor(cell, cells, top=True), global_ground=global_ground),
        ]
        for side in ("east", "west", "north", "south"):
            breaks = side_breaks(cell, side, cells)
            for a1, a2 in zip(breaks, breaks[1:]):
                if a2 - a1 <= TOL:
                    continue
                neighbor = vertical_neighbor(cell, side, 0.5 * (a1 + a2), cell.cz, cells)
                vertices, plane, constant, span_a = wall_vertices(cell, side, a1, a2)
                if neighbor is None:
                    zone_surfaces.append(Surface("", "Wall", "EXT_WALL", cell.name, "Outdoors", "", True, True, vertices, plane, constant, span_a, (cell.zmin, cell.zmax), side, False))
                else:
                    internal_split = neighbor.source_zone == cell.source_zone
                    zone_surfaces.append(Surface("", "Wall", "ADJ_WALL", cell.name, "Zone", neighbor.name, False, False, vertices, plane, constant, span_a, (cell.zmin, cell.zmax), side, internal_split))
        for surface_index, surface in enumerate(zone_surfaces, 1):
            surface.surface_id = f"s{zone_index:02d}_{surface_index:03d}"
            surfaces.append(surface)
    return surfaces


def assign_window_parents(cells: Sequence[Cell], surfaces: Sequence[Surface]) -> Tuple[List[Window], int]:
    exterior_by_zone: Dict[str, List[Surface]] = {}
    for surface in surfaces:
        if surface.construction == "EXT_WALL":
            exterior_by_zone.setdefault(surface.zone_name, []).append(surface)
    assigned: List[Window] = []
    dropped = 0
    for cell in cells:
        window_index = 1
        for window in cell.windows:
            parent = find_parent_surface(window, exterior_by_zone.get(cell.name, []))
            if parent is None:
                dropped += 1
                continue
            safe_zone_name = re.sub(r"[^A-Za-z0-9_]", "_", cell.name)
            window.final_id = f"w_{safe_zone_name}_{window_index:03d}"
            window.parent_surface = parent.surface_id
            assigned.append(window)
            window_index += 1
    return assigned, dropped


def find_parent_surface(window: Window, surfaces: Sequence[Surface]) -> Optional[Surface]:
    for surface in surfaces:
        if surface.plane != window.plane or surface.constant is None or surface.span_a is None or surface.span_z is None:
            continue
        if not near(surface.constant, window.constant, 1.0e-5):
            continue
        if not (inside_closed(window.axis_min, surface.span_a[0], surface.span_a[1]) and inside_closed(window.axis_max, surface.span_a[0], surface.span_a[1])):
            continue
        if not (inside_closed(window.zmin, surface.span_z[0], surface.span_z[1]) and inside_closed(window.zmax, surface.span_z[0], surface.span_z[1])):
            continue
        return surface
    return None


def render_geometry(cells: Sequence[Cell], surfaces: Sequence[Surface], windows: Sequence[Window]) -> str:
    surfaces_by_zone: Dict[str, List[Surface]] = {}
    windows_by_zone: Dict[str, List[Window]] = {}
    for surface in surfaces:
        surfaces_by_zone.setdefault(surface.zone_name, []).append(surface)
    for cell in cells:
        for window in cell.windows:
            if window.parent_surface:
                windows_by_zone.setdefault(cell.name, []).append(window)

    chunks: List[str] = []
    for cell in sorted(cells, key=lambda c: (c.zmin, c.xmin, c.ymin, c.name)):
        chunks.append(
            f"""Zone,
    {cell.name},
    0.0,
    0.0,
    0.0,
    0.0,
    ,
    1;
"""
        )
        for surface in surfaces_by_zone.get(cell.name, []):
            chunks.append(render_surface(surface))
        for window in windows_by_zone.get(cell.name, []):
            chunks.append(render_window(window))
    return "\n".join(chunks).rstrip() + "\n"


def render_surface(surface: Surface) -> str:
    vertex_lines = []
    for index, (x, y, z) in enumerate(surface.vertices, 1):
        terminator = ";" if index == len(surface.vertices) else ","
        vertex_lines.append(f"    {fmt(x)},\n    {fmt(y)},\n    {fmt(z)}{terminator}")
    return f"""  BuildingSurface:Detailed,
    {surface.surface_id},
    {surface.surface_type},
    {surface.construction},
    {surface.zone_name},
    {surface.boundary_cond},
    {surface.boundary_obj},
    {'SunExposed' if surface.sun else 'NoSun'},
    {'WindExposed' if surface.wind else 'NoWind'},
    ,
    {len(surface.vertices)},
{chr(10).join(vertex_lines)}
"""


def render_window(window: Window) -> str:
    vertex_lines = []
    for index, (x, y, z) in enumerate(window.vertices, 1):
        terminator = ";" if index == len(window.vertices) else ","
        vertex_lines.append(f"    {fmt(x)},\n    {fmt(y)},\n    {fmt(z)}{terminator}")
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
{chr(10).join(vertex_lines)}
"""


def write_with_template(template: Path, output: Path, geometry: str) -> None:
    text = read_text(template)
    match = re.search(r"(?im)^\s*Zone\s*,\s*$", text)
    prefix = text[: match.start()].rstrip() if match else text.rstrip()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prefix + "\n\n" + geometry.rstrip() + "\n", encoding="utf-8")


def default_template_for_source(source: Path) -> Path:
    candidate = source.parent / "Empty_Zone_Template_01_06.idf"
    if candidate.exists():
        return candidate
    matches = list(source.parent.glob("*.idf"))
    if not matches:
        raise FileNotFoundError(f"No IDF template was found next to {source}")
    return matches[0]


def validate(original_zones: Sequence[OriginalZone], cells: Sequence[Cell], surfaces: Sequence[Surface], windows: Sequence[Window], dropped_windows: int) -> List[str]:
    errors: List[str] = []
    names = [cell.name for cell in cells]
    if len(names) != len(set(names)):
        errors.append("Duplicate final zone names detected")
    surface_ids = [surface.surface_id for surface in surfaces]
    if len(surface_ids) != len(set(surface_ids)):
        errors.append("Duplicate BuildingSurface IDs detected")
    window_ids = [window.final_id for window in windows]
    if len(window_ids) != len(set(window_ids)):
        errors.append("Duplicate FenestrationSurface IDs detected")
    parent_ids = {surface.surface_id for surface in surfaces}
    for window in windows:
        if window.parent_surface not in parent_ids:
            errors.append(f"Window {window.final_id} points to missing parent {window.parent_surface}")
    for cell in cells:
        if cell.xmax - cell.xmin <= TOL or cell.ymax - cell.ymin <= TOL or cell.zmax - cell.zmin <= TOL:
            errors.append(f"Final zone {cell.name} has zero thickness")
    if dropped_windows:
        pass
    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split selected compressed IDF thermal zones by x/y distances and regenerate IDF geometry.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", required=True, help="Original ex*.py source")
    parser.add_argument("--template", help="IDF template; defaults to the IDF beside --source")
    parser.add_argument("--output", required=True, help="Output IDF path")
    parser.add_argument("--report", help="Optional JSON report path")
    parser.add_argument(
        "--split",
        action="append",
        required=True,
        help="Split spec: zone:axis:distances, e.g. zone03:x:3,6 or 3:y:2.5. Axis x/ew is distance from west wall; y/ns is distance from south wall.",
    )
    parser.add_argument("--sync-vertical", action="store_true", help="Apply each split to zones above/below with the same footprint")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source = Path(args.source)
    template = Path(args.template) if args.template else default_template_for_source(source)
    output = Path(args.output)

    try:
        original_zones = load_zones(source)
        split_map = parse_split_specs(args.split, original_zones, args.sync_vertical)
        cells = split_zones(original_zones, split_map)
        surfaces = build_surfaces(cells)
        windows, dropped_windows = assign_window_parents(cells, surfaces)
        errors = validate(original_zones, cells, surfaces, windows, dropped_windows)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 2
        geometry = render_geometry(cells, surfaces, windows)
        write_with_template(template, output, geometry)

        source_counts: Dict[str, int] = {}
        for cell in cells:
            source_counts[cell.source_zone] = source_counts.get(cell.source_zone, 0) + 1
        split_zone_names = sorted(name for name, count in source_counts.items() if count > 1)
        report = {
            "source": str(source),
            "template": str(template),
            "output": str(output),
            "split_specs": args.split,
            "sync_vertical": args.sync_vertical,
            "original_zones": len(original_zones),
            "final_zones": len(cells),
            "split_source_zones": split_zone_names,
            "building_surfaces": len(surfaces),
            "internal_split_wall_surfaces": sum(1 for surface in surfaces if surface.internal_split_wall),
            "fenestration_surfaces": len(windows),
            "dropped_windows": dropped_windows,
            "window_pieces_by_source": window_piece_counts(windows),
        }
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def window_piece_counts(windows: Sequence[Window]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for window in windows:
        counts[window.source_id] = counts.get(window.source_id, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
