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


def positive_overlap(a1: float, a2: float, b1: float, b2: float) -> bool:
    return min(a2, b2) - max(a1, b1) > TOL


def inside_closed(value: float, low: float, high: float) -> bool:
    return low - TOL <= value <= high + TOL


@dataclass
class Window:
    source_id: str
    construction: str
    parent_source_id: str
    side: str
    axis_min: float
    axis_max: float
    zmin: float
    zmax: float
    plane: str
    constant: float
    source_zone: str
    vertices: List[Point3] = field(default_factory=list)
    final_id: str = ""
    parent_surface: str = ""


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
    def volume(self) -> float:
        return (self.xmax - self.xmin) * (self.ymax - self.ymin) * (self.zmax - self.zmin)


@dataclass
class FinalZone:
    name: str
    source_zones: List[str]
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    windows: List[Window] = field(default_factory=list)

    @property
    def volume(self) -> float:
        return (self.xmax - self.xmin) * (self.ymax - self.ymin) * (self.zmax - self.zmin)

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
    side: str
    plane: Optional[str] = None
    constant: Optional[float] = None
    span_a: Optional[Tuple[float, float]] = None
    span_z: Optional[Tuple[float, float]] = None


class UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, a: str, b: str) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


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


def zone_number(name: str) -> Optional[int]:
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else None


def detect_window(vertices: Sequence[Point3], zone: OriginalZone) -> Tuple[str, str, float, float, float, float, float]:
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
    side, plane, constant, axis_min, axis_max, zmin, zmax = detect_window(vertices, zone)
    return Window(
        source_id=parts[0],
        construction=parts[1],
        parent_source_id=parts[2],
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
    for zone_tuple in extract_zones_from_python(source):
        name = str(zone_tuple[0])
        vertices = [tuple(map(float, point)) for point in zone_tuple[1]]
        xs = [p[0] for p in vertices]
        ys = [p[1] for p in vertices]
        zs = [p[2] for p in vertices]
        zone = OriginalZone(name, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
        for def_item in zone_tuple[2:]:
            if isinstance(def_item, str):
                window = parse_window(def_item, zone)
                if window is not None:
                    zone.windows.append(window)
        zones.append(zone)
    return zones


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
    if value in ("auto", ""):
        return "auto"
    if value in ("x", "ew", "east-west", "west", "from-west"):
        return "x"
    if value in ("y", "ns", "north-south", "south", "from-south"):
        return "y"
    if value in ("z", "vertical", "height", "from-bottom"):
        return "z"
    raise ValueError(f"Unknown merge axis {axis!r}; use x/y/z/auto")


def adjacency_axis(a: OriginalZone, b: OriginalZone) -> Tuple[str, float, float]:
    if (near(a.ymin, b.ymin) and near(a.ymax, b.ymax) and near(a.zmin, b.zmin) and near(a.zmax, b.zmax)):
        if near(a.xmax, b.xmin):
            return "x", a.xmax, min(a.xmin, b.xmin)
        if near(b.xmax, a.xmin):
            return "x", b.xmax, min(a.xmin, b.xmin)
    if (near(a.xmin, b.xmin) and near(a.xmax, b.xmax) and near(a.zmin, b.zmin) and near(a.zmax, b.zmax)):
        if near(a.ymax, b.ymin):
            return "y", a.ymax, min(a.ymin, b.ymin)
        if near(b.ymax, a.ymin):
            return "y", b.ymax, min(a.ymin, b.ymin)
    if (near(a.xmin, b.xmin) and near(a.xmax, b.xmax) and near(a.ymin, b.ymin) and near(a.ymax, b.ymax)):
        if near(a.zmax, b.zmin):
            return "z", a.zmax, min(a.zmin, b.zmin)
        if near(b.zmax, a.zmin):
            return "z", b.zmax, min(a.zmin, b.zmin)
    raise ValueError(f"{a.name} and {b.name} are not full-face adjacent rectangular zones")


def parse_merge_specs(specs: Sequence[str], zones: Sequence[OriginalZone]) -> List[Tuple[str, str]]:
    zone_by_name = {zone.name: zone for zone in zones}
    pairs: List[Tuple[str, str]] = []
    for spec in specs:
        parts = [part.strip() for part in spec.split(":")]
        pair_part = parts[0]
        if "+" in pair_part:
            left_ref, right_ref = [part.strip() for part in pair_part.split("+", 1)]
        elif "," in pair_part:
            left_ref, right_ref = [part.strip() for part in pair_part.split(",", 1)]
        else:
            raise ValueError(f"Merge spec must start with zoneA+zoneB, got {spec!r}")
        left = resolve_zone_ref(left_ref, zones)
        right = resolve_zone_ref(right_ref, zones)
        if left == right:
            raise ValueError(f"Cannot merge {left} with itself")

        detected_axis, shared_coordinate, origin_coordinate = adjacency_axis(zone_by_name[left], zone_by_name[right])
        requested_axis = normalize_axis(parts[1]) if len(parts) >= 2 else "auto"
        if requested_axis != "auto" and requested_axis != detected_axis:
            raise ValueError(f"Merge {spec!r} uses axis {requested_axis}, but the shared wall is on axis {detected_axis}")
        if len(parts) >= 3 and parts[2] and parts[2].lower() != "auto":
            requested_distance = float(parts[2])
            actual_distance = shared_coordinate - origin_coordinate
            if not near(requested_distance, actual_distance, 1.0e-5):
                raise ValueError(f"Merge {spec!r} distance mismatch: requested {requested_distance:g}, actual {actual_distance:g}")
        pairs.append((left, right))
    return pairs


def build_final_zones(zones: Sequence[OriginalZone], pairs: Sequence[Tuple[str, str]]) -> List[FinalZone]:
    zone_by_name = {zone.name: zone for zone in zones}
    uf = UnionFind(zone.name for zone in zones)
    for left, right in pairs:
        uf.union(left, right)
    groups: Dict[str, List[OriginalZone]] = {}
    for zone in zones:
        groups.setdefault(uf.find(zone.name), []).append(zone)

    final_zones: List[FinalZone] = []
    for group in groups.values():
        group = sorted(group, key=lambda z: (z.zmin, z.xmin, z.ymin, z.name))
        xmin, xmax = min(z.xmin for z in group), max(z.xmax for z in group)
        ymin, ymax = min(z.ymin for z in group), max(z.ymax for z in group)
        zmin, zmax = min(z.zmin for z in group), max(z.zmax for z in group)
        bbox_volume = (xmax - xmin) * (ymax - ymin) * (zmax - zmin)
        sum_volume = sum(z.volume for z in group)
        if not near(bbox_volume, sum_volume, 1.0e-5):
            names = [z.name for z in group]
            raise ValueError(f"Merged group {names} does not form one clean rectangular cuboid")
        name = group[0].name if len(group) == 1 else "_".join(z.name for z in group)
        final_zones.append(FinalZone(name, [z.name for z in group], xmin, xmax, ymin, ymax, zmin, zmax))
    final_zones.sort(key=lambda z: (z.zmin, z.xmin, z.ymin, z.name))
    return final_zones


def face_area(zone: FinalZone, side: str) -> float:
    if side in ("east", "west"):
        return (zone.ymax - zone.ymin) * (zone.zmax - zone.zmin)
    if side in ("north", "south"):
        return (zone.xmax - zone.xmin) * (zone.zmax - zone.zmin)
    return (zone.xmax - zone.xmin) * (zone.ymax - zone.ymin)


def overlap_area_on_face(zone: FinalZone, other: FinalZone, side: str) -> float:
    if side in ("east", "west"):
        if side == "east" and not near(other.xmin, zone.xmax):
            return 0.0
        if side == "west" and not near(other.xmax, zone.xmin):
            return 0.0
        if not (positive_overlap(zone.ymin, zone.ymax, other.ymin, other.ymax) and positive_overlap(zone.zmin, zone.zmax, other.zmin, other.zmax)):
            return 0.0
        return (min(zone.ymax, other.ymax) - max(zone.ymin, other.ymin)) * (min(zone.zmax, other.zmax) - max(zone.zmin, other.zmin))
    if side in ("north", "south"):
        if side == "north" and not near(other.ymin, zone.ymax):
            return 0.0
        if side == "south" and not near(other.ymax, zone.ymin):
            return 0.0
        if not (positive_overlap(zone.xmin, zone.xmax, other.xmin, other.xmax) and positive_overlap(zone.zmin, zone.zmax, other.zmin, other.zmax)):
            return 0.0
        return (min(zone.xmax, other.xmax) - max(zone.xmin, other.xmin)) * (min(zone.zmax, other.zmax) - max(zone.zmin, other.zmin))
    if side == "top":
        if not near(other.zmin, zone.zmax):
            return 0.0
    else:
        if not near(other.zmax, zone.zmin):
            return 0.0
    if not (positive_overlap(zone.xmin, zone.xmax, other.xmin, other.xmax) and positive_overlap(zone.ymin, zone.ymax, other.ymin, other.ymax)):
        return 0.0
    return (min(zone.xmax, other.xmax) - max(zone.xmin, other.xmin)) * (min(zone.ymax, other.ymax) - max(zone.ymin, other.ymin))


def whole_face_neighbor(zone: FinalZone, side: str, all_zones: Sequence[FinalZone]) -> Optional[FinalZone]:
    overlaps: List[Tuple[FinalZone, float]] = []
    for other in all_zones:
        if other.name == zone.name:
            continue
        area = overlap_area_on_face(zone, other, side)
        if area > TOL:
            overlaps.append((other, area))
    if not overlaps:
        return None
    full_area = face_area(zone, side)
    if len(overlaps) == 1 and near(overlaps[0][1], full_area, 1.0e-5):
        return overlaps[0][0]
    detail = [(other.name, area) for other, area in overlaps]
    raise ValueError(
        f"Final zone {zone.name} face {side} cannot be represented as one IDF surface with one boundary object. "
        f"Overlaps: {detail}. Merge the corresponding neighbor zones too."
    )


def make_surface(zone: FinalZone, side: str, neighbor: Optional[FinalZone], global_ground: float) -> Surface:
    x1, x2, y1, y2, z1, z2 = zone.xmin, zone.xmax, zone.ymin, zone.ymax, zone.zmin, zone.zmax
    if side == "bottom":
        vertices = [(x1, y1, z1), (x1, y2, z1), (x2, y2, z1), (x2, y1, z1)]
        if neighbor is not None:
            return Surface("", "Floor", "ADJ_CEILING", zone.name, "Zone", neighbor.name, False, False, vertices, side)
        if near(z1, global_ground):
            return Surface("", "Floor", "GROUND_FLOOR", zone.name, "Ground", "BOUNDARY=INPUT 1*TGROUND", False, False, vertices, side)
        return Surface("", "Floor", "EXT_FLOOR", zone.name, "Outdoors", "", True, True, vertices, side)
    if side == "top":
        vertices = [(x2, y1, z2), (x2, y2, z2), (x1, y2, z2), (x1, y1, z2)]
        if neighbor is not None:
            return Surface("", "Ceiling", "ADJ_CEILING", zone.name, "Zone", neighbor.name, False, False, vertices, side)
        return Surface("", "Roof", "EXT_ROOF", zone.name, "Outdoors", "", True, True, vertices, side)
    if side == "east":
        vertices = [(x2, y2, z2), (x2, y1, z2), (x2, y1, z1), (x2, y2, z1)]
        plane, constant, span_a = "x", x2, (y1, y2)
    elif side == "west":
        vertices = [(x1, y2, z1), (x1, y1, z1), (x1, y1, z2), (x1, y2, z2)]
        plane, constant, span_a = "x", x1, (y1, y2)
    elif side == "north":
        vertices = [(x2, y2, z1), (x1, y2, z1), (x1, y2, z2), (x2, y2, z2)]
        plane, constant, span_a = "y", y2, (x1, x2)
    elif side == "south":
        vertices = [(x1, y1, z1), (x2, y1, z1), (x2, y1, z2), (x1, y1, z2)]
        plane, constant, span_a = "y", y1, (x1, x2)
    else:
        raise ValueError(f"Unknown side: {side}")
    if neighbor is not None:
        return Surface("", "Wall", "ADJ_WALL", zone.name, "Zone", neighbor.name, False, False, vertices, side, plane, constant, span_a, (z1, z2))
    return Surface("", "Wall", "EXT_WALL", zone.name, "Outdoors", "", True, True, vertices, side, plane, constant, span_a, (z1, z2))


def build_surfaces(final_zones: Sequence[FinalZone]) -> List[Surface]:
    surfaces: List[Surface] = []
    global_ground = min(zone.zmin for zone in final_zones)
    for zone_index, zone in enumerate(final_zones, 1):
        zone_surfaces = []
        for side in ("bottom", "top", "east", "west", "north", "south"):
            neighbor = whole_face_neighbor(zone, side, final_zones)
            zone_surfaces.append(make_surface(zone, side, neighbor, global_ground))
        for surface_index, surface in enumerate(zone_surfaces, 1):
            surface.surface_id = f"s{zone_index:02d}_{surface_index:03d}"
            surfaces.append(surface)
    return surfaces


def collect_windows(final_zones: Sequence[FinalZone], original_zones: Sequence[OriginalZone], surfaces: Sequence[Surface]) -> Tuple[List[Window], int, int]:
    original_by_name = {zone.name: zone for zone in original_zones}
    exterior_side_by_zone: Dict[Tuple[str, str], Surface] = {
        (surface.zone_name, surface.side): surface
        for surface in surfaces
        if surface.construction == "EXT_WALL"
    }
    candidate_count = 0
    merged_windows: List[Window] = []
    dropped = 0
    for final_zone in final_zones:
        candidates: List[Window] = []
        for source_name in final_zone.source_zones:
            source_zone = original_by_name[source_name]
            for window in source_zone.windows:
                if window.side not in ("south", "north", "west", "east"):
                    dropped += 1
                    continue
                if not window_on_final_exterior(window, final_zone):
                    continue
                candidates.append(window)
        candidate_count += len(candidates)
        for window in merge_touching_windows(final_zone, candidates):
            parent = exterior_side_by_zone.get((final_zone.name, window.side))
            if parent is None:
                dropped += 1
                continue
            window.parent_surface = parent.surface_id
            window.vertices = window_vertices(window)
            merged_windows.append(window)
    for index, window in enumerate(merged_windows, 1):
        safe_zone = re.sub(r"[^A-Za-z0-9_]", "_", window.source_zone)
        window.final_id = f"w_{safe_zone}_{index:03d}"
    return merged_windows, dropped, candidate_count


def window_on_final_exterior(window: Window, zone: FinalZone) -> bool:
    if window.side == "south":
        return near(window.constant, zone.ymin) and inside_closed(window.axis_min, zone.xmin, zone.xmax) and inside_closed(window.axis_max, zone.xmin, zone.xmax)
    if window.side == "north":
        return near(window.constant, zone.ymax) and inside_closed(window.axis_min, zone.xmin, zone.xmax) and inside_closed(window.axis_max, zone.xmin, zone.xmax)
    if window.side == "west":
        return near(window.constant, zone.xmin) and inside_closed(window.axis_min, zone.ymin, zone.ymax) and inside_closed(window.axis_max, zone.ymin, zone.ymax)
    if window.side == "east":
        return near(window.constant, zone.xmax) and inside_closed(window.axis_min, zone.ymin, zone.ymax) and inside_closed(window.axis_max, zone.ymin, zone.ymax)
    return False


def merge_touching_windows(final_zone: FinalZone, windows: Sequence[Window]) -> List[Window]:
    grouped: Dict[Tuple[str, str, float, float, float, str], List[Window]] = {}
    for window in windows:
        group_key = (window.side, window.plane, key(window.constant), key(window.zmin), key(window.zmax), window.construction)
        grouped.setdefault(group_key, []).append(window)
    result: List[Window] = []
    for group in grouped.values():
        group.sort(key=lambda w: (w.axis_min, w.axis_max, w.source_id))
        active: Optional[Window] = None
        source_ids: List[str] = []
        for window in group:
            if active is None:
                active = clone_window_for_final(window, final_zone)
                source_ids = [window.source_id]
                continue
            if near(active.axis_max, window.axis_min, 1.0e-6):
                active.axis_max = max(active.axis_max, window.axis_max)
                source_ids.append(window.source_id)
                active.source_id = "+".join(source_ids)
            else:
                result.append(active)
                active = clone_window_for_final(window, final_zone)
                source_ids = [window.source_id]
        if active is not None:
            result.append(active)
    return result


def clone_window_for_final(window: Window, final_zone: FinalZone) -> Window:
    return Window(
        source_id=window.source_id,
        construction=window.construction,
        parent_source_id=window.parent_source_id,
        side=window.side,
        axis_min=window.axis_min,
        axis_max=window.axis_max,
        zmin=window.zmin,
        zmax=window.zmax,
        plane=window.plane,
        constant=window.constant,
        source_zone=final_zone.name,
    )


def window_vertices(window: Window) -> List[Point3]:
    a1, a2, z1, z2 = window.axis_min, window.axis_max, window.zmin, window.zmax
    if window.side == "south":
        y = window.constant
        return [(a1, y, z2), (a1, y, z1), (a2, y, z1), (a2, y, z2)]
    if window.side == "north":
        y = window.constant
        return [(a1, y, z1), (a1, y, z2), (a2, y, z2), (a2, y, z1)]
    if window.side == "west":
        x = window.constant
        return [(x, a2, z1), (x, a1, z1), (x, a1, z2), (x, a2, z2)]
    if window.side == "east":
        x = window.constant
        return [(x, a2, z2), (x, a1, z2), (x, a1, z1), (x, a2, z1)]
    raise ValueError(f"Unknown window side: {window.side}")


def render_geometry(final_zones: Sequence[FinalZone], surfaces: Sequence[Surface], windows: Sequence[Window]) -> str:
    surfaces_by_zone: Dict[str, List[Surface]] = {}
    windows_by_zone: Dict[str, List[Window]] = {}
    for surface in surfaces:
        surfaces_by_zone.setdefault(surface.zone_name, []).append(surface)
    for window in windows:
        parent_surface = next((surface for surface in surfaces if surface.surface_id == window.parent_surface), None)
        if parent_surface is not None:
            windows_by_zone.setdefault(parent_surface.zone_name, []).append(window)
    chunks: List[str] = []
    for zone in final_zones:
        chunks.append(
            f"""Zone,
    {zone.name},
    0.0,
    0.0,
    0.0,
    0.0,
    ,
    1;
"""
        )
        for surface in surfaces_by_zone.get(zone.name, []):
            chunks.append(render_surface(surface))
        for window in windows_by_zone.get(zone.name, []):
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


def validate(final_zones: Sequence[FinalZone], surfaces: Sequence[Surface], windows: Sequence[Window]) -> List[str]:
    errors: List[str] = []
    zone_names = [zone.name for zone in final_zones]
    if len(zone_names) != len(set(zone_names)):
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
    per_zone_surface_count: Dict[str, int] = {}
    for surface in surfaces:
        per_zone_surface_count[surface.zone_name] = per_zone_surface_count.get(surface.zone_name, 0) + 1
    for zone in final_zones:
        if per_zone_surface_count.get(zone.name, 0) != 6:
            errors.append(f"Final zone {zone.name} has {per_zone_surface_count.get(zone.name, 0)} surfaces, expected 6")
    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge selected full-face-adjacent rectangular IDF zones while keeping each final zone at six surfaces.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", required=True, help="Original ex*.py source")
    parser.add_argument("--template", help="IDF template; defaults to the IDF beside --source")
    parser.add_argument("--output", required=True, help="Output IDF path")
    parser.add_argument("--report", help="Optional JSON report path")
    parser.add_argument(
        "--merge",
        action="append",
        required=True,
        help="Merge spec: zoneA+zoneB[:axis[:distance]], e.g. zone03+zone04:x:8.1 or zone03+zone04:auto",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source = Path(args.source)
    template = Path(args.template) if args.template else default_template_for_source(source)
    output = Path(args.output)
    try:
        original_zones = load_zones(source)
        pairs = parse_merge_specs(args.merge, original_zones)
        final_zones = build_final_zones(original_zones, pairs)
        surfaces = build_surfaces(final_zones)
        windows, dropped_windows, candidate_window_count = collect_windows(final_zones, original_zones, surfaces)
        errors = validate(final_zones, surfaces, windows)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 2
        geometry = render_geometry(final_zones, surfaces, windows)
        write_with_template(template, output, geometry)
        merged_groups = [zone.source_zones for zone in final_zones if len(zone.source_zones) > 1]
        report = {
            "source": str(source),
            "template": str(template),
            "output": str(output),
            "merge_specs": args.merge,
            "merge_pairs": [{"left": left, "right": right} for left, right in pairs],
            "original_zones": len(original_zones),
            "final_zones": len(final_zones),
            "merged_groups": merged_groups,
            "building_surfaces": len(surfaces),
            "surfaces_per_zone": 6,
            "candidate_windows_on_kept_faces": candidate_window_count,
            "fenestration_surfaces": len(windows),
            "merged_window_reductions": candidate_window_count - len(windows),
            "dropped_windows": dropped_windows,
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


if __name__ == "__main__":
    raise SystemExit(main())
