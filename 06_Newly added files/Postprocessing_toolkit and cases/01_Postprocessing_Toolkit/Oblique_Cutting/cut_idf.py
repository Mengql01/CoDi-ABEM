#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Point2 = Tuple[float, float]
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


def signed_area(poly: Sequence[Point2]) -> float:
    area = 0.0
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
    return 0.5 * area


def polygon_centroid(poly: Sequence[Point2]) -> Point2:
    area = signed_area(poly)
    if abs(area) <= TOL:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    cx = 0.0
    cy = 0.0
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    factor = 1.0 / (6.0 * area)
    return (cx * factor, cy * factor)


def remove_duplicate_points(poly: List[Point2]) -> List[Point2]:
    result: List[Point2] = []
    for point in poly:
        if not result or not (near(point[0], result[-1][0]) and near(point[1], result[-1][1])):
            result.append(point)
    if len(result) > 1 and near(result[0][0], result[-1][0]) and near(result[0][1], result[-1][1]):
        result.pop()
    return result


def remove_collinear(poly: List[Point2]) -> List[Point2]:
    poly = remove_duplicate_points(poly)
    changed = True
    while changed and len(poly) > 3:
        changed = False
        cleaned: List[Point2] = []
        n = len(poly)
        for i, point in enumerate(poly):
            prev = poly[(i - 1) % n]
            nxt = poly[(i + 1) % n]
            cross = (point[0] - prev[0]) * (nxt[1] - point[1]) - (point[1] - prev[1]) * (nxt[0] - point[0])
            if abs(cross) <= TOL:
                changed = True
                continue
            cleaned.append(point)
        poly = cleaned
    return poly


def point_in_polygon(point: Point2, poly: Sequence[Point2]) -> bool:
    x, y = point
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > y) != (y2 > y)):
            x_at_y = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_at_y:
                inside = not inside
    return inside


def distance_point_to_line(point: Point2, a: Point2, b: Point2) -> float:
    px, py = point
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    length = math.hypot(dx, dy)
    if length <= TOL:
        return math.hypot(px - ax, py - ay)
    return abs((px - ax) * dy - (py - ay) * dx) / length


def point_on_segment(point: Point2, a: Point2, b: Point2) -> bool:
    if distance_point_to_line(point, a, b) > 1.0e-5:
        return False
    return (
        min(a[0], b[0]) - 1.0e-5 <= point[0] <= max(a[0], b[0]) + 1.0e-5
        and min(a[1], b[1]) - 1.0e-5 <= point[1] <= max(a[1], b[1]) + 1.0e-5
    )


def polygons_overlap_by_centroid(a: Sequence[Point2], b: Sequence[Point2]) -> bool:
    ca = polygon_centroid(a)
    cb = polygon_centroid(b)
    return point_in_polygon(ca, b) or point_in_polygon(cb, a)


@dataclass
class CutLine:
    x0: float
    y0: float
    slope: float
    description: str

    def y_at(self, x: float) -> float:
        return self.y0 + self.slope * (x - self.x0)


@dataclass
class Window:
    source_id: str
    construction: str
    parent_source_id: str
    original_vertices: List[Point3]
    vertices: List[Point3]
    source_side: str
    final_id: str = ""
    parent_surface: str = ""
    projected: bool = False
    max_x_shift: float = 0.0


@dataclass
class ZonePrism:
    name: str
    original_polygon: List[Point2]
    polygon: List[Point2]
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    windows: List[Window] = field(default_factory=list)
    original_area: float = 0.0

    @property
    def area(self) -> float:
        return abs(signed_area(self.polygon))


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
    edge_start: Optional[Point2] = None
    edge_end: Optional[Point2] = None
    zmin: Optional[float] = None
    zmax: Optional[float] = None


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


def parse_window(def_item: str, zone_bounds: Tuple[float, float, float, float], zmin: float, zmax: float) -> Optional[Window]:
    parts = [part.strip() for part in def_item.split(",", 3)]
    if len(parts) < 4 or parts[1] != "EXT_WINDOW1":
        return None
    vertices = [
        tuple(float(piece) for piece in match.strip("()").split(","))  # type: ignore[misc]
        for match in re.findall(r"\([^)]+\)", parts[3])
    ]
    xmin, xmax, ymin, ymax = zone_bounds
    side = detect_window_side(vertices, xmin, xmax, ymin, ymax)
    return Window(
        source_id=parts[0],
        construction=parts[1],
        parent_source_id=parts[2],
        original_vertices=vertices,  # type: ignore[arg-type]
        vertices=list(vertices),  # type: ignore[arg-type]
        source_side=side,
    )


def detect_window_side(vertices: Sequence[Point3], xmin: float, xmax: float, ymin: float, ymax: float) -> str:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    if max(ys) - min(ys) <= 1.0e-5:
        if near(sum(ys) / len(ys), ymin, 1.0e-5):
            return "south"
        if near(sum(ys) / len(ys), ymax, 1.0e-5):
            return "north"
    if max(xs) - min(xs) <= 1.0e-5:
        if near(sum(xs) / len(xs), xmin, 1.0e-5):
            return "west"
        if near(sum(xs) / len(xs), xmax, 1.0e-5):
            return "east"
    return "unknown"


def load_zones(source: Path) -> List[ZonePrism]:
    zones: List[ZonePrism] = []
    for zone_tuple in extract_zones_from_python(source):
        name = str(zone_tuple[0])
        vertices = [tuple(map(float, point)) for point in zone_tuple[1]]
        xs = [p[0] for p in vertices]
        ys = [p[1] for p in vertices]
        zs = [p[2] for p in vertices]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        zmin, zmax = min(zs), max(zs)
        footprint = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        windows: List[Window] = []
        for def_item in zone_tuple[2:]:
            if isinstance(def_item, str):
                window = parse_window(def_item, (xmin, xmax, ymin, ymax), zmin, zmax)
                if window is not None:
                    windows.append(window)
        zones.append(
            ZonePrism(
                name=name,
                original_polygon=footprint,
                polygon=footprint,
                xmin=xmin,
                xmax=xmax,
                ymin=ymin,
                ymax=ymax,
                zmin=zmin,
                zmax=zmax,
                windows=windows,
                original_area=abs(signed_area(footprint)),
            )
        )
    return zones


def model_bounds(zones: Sequence[ZonePrism]) -> Tuple[float, float, float, float]:
    return (
        min(zone.xmin for zone in zones),
        max(zone.xmax for zone in zones),
        min(zone.ymin for zone in zones),
        max(zone.ymax for zone in zones),
    )


def build_cut_line(args: argparse.Namespace, zones: Sequence[ZonePrism]) -> CutLine:
    xmin, xmax, ymin, ymax = model_bounds(zones)
    width = xmax - xmin
    depth = ymax - ymin
    if width <= TOL or depth <= TOL:
        raise ValueError("Model width/depth is too small for cutting")

    y0 = ymin + args.west_offset
    if args.line_mode == "absolute":
        if args.cosine is not None:
            angle = math.degrees(math.acos(args.cosine))
        else:
            angle = args.angle
        slope = math.tan(math.radians(angle))
        return CutLine(x0=xmin, y0=y0, slope=slope, description=f"absolute angle={angle:g} deg")

    if args.cut_depth is not None:
        cut_depth = args.cut_depth
        source = f"cut_depth={cut_depth:g} m"
    elif args.cut_ratio is not None:
        cut_depth = depth * args.cut_ratio
        source = f"cut_ratio={args.cut_ratio:g}"
    elif args.cosine is not None:
        cut_depth = depth * args.cosine
        source = f"cosine={args.cosine:g}"
    else:
        cut_depth = depth * math.sin(math.radians(args.angle))
        source = f"angle={args.angle:g} deg, normalized north component=sin(angle)"
    slope = cut_depth / width
    return CutLine(x0=xmin, y0=y0, slope=slope, description=source)


def clip_polygon_with_south_cut(poly: Sequence[Point2], cut_line: CutLine) -> List[Point2]:
    def inside(point: Point2) -> bool:
        return point[1] >= cut_line.y_at(point[0]) - TOL

    def intersection(a: Point2, b: Point2) -> Point2:
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        denominator = dy - cut_line.slope * dx
        if abs(denominator) <= TOL:
            return b
        t = (cut_line.y_at(ax) - ay) / denominator
        t = max(0.0, min(1.0, t))
        return (ax + t * dx, ay + t * dy)

    output = list(poly)
    if not output:
        return []
    clipped: List[Point2] = []
    previous = output[-1]
    previous_inside = inside(previous)
    for current in output:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                clipped.append(intersection(previous, current))
            clipped.append(current)
        elif previous_inside:
            clipped.append(intersection(previous, current))
        previous = current
        previous_inside = current_inside
    clipped = remove_collinear(clipped)
    if len(clipped) >= 3 and signed_area(clipped) < 0:
        clipped = list(reversed(clipped))
    return clipped


def apply_cut(zones: Sequence[ZonePrism], cut_line: CutLine, allow_removed_zones: bool) -> List[ZonePrism]:
    kept: List[ZonePrism] = []
    for zone in zones:
        clipped = clip_polygon_with_south_cut(zone.original_polygon, cut_line)
        if len(clipped) < 3 or abs(signed_area(clipped)) <= TOL:
            if allow_removed_zones:
                continue
            raise ValueError(f"Cut removed {zone.name}. Use a smaller cut or --allow-removed-zones.")
        zone.polygon = clipped
        project_zone_windows(zone, cut_line)
        kept.append(zone)
    return kept


def project_zone_windows(zone: ZonePrism, cut_line: CutLine) -> None:
    for window in zone.windows:
        if window.source_side != "south":
            continue
        projected: List[Point3] = []
        max_shift = 0.0
        for original, current in zip(window.original_vertices, window.vertices):
            x, _, z = current
            projected.append((x, cut_line.y_at(x), z))
            max_shift = max(max_shift, abs(original[0] - x))
        window.vertices = projected
        window.projected = True
        window.max_x_shift = max_shift


def horizontal_neighbor(zone: ZonePrism, zones: Sequence[ZonePrism], top: bool) -> Optional[ZonePrism]:
    z = zone.zmax if top else zone.zmin
    for other in zones:
        if other.name == zone.name:
            continue
        plane_match = near(other.zmin, z) if top else near(other.zmax, z)
        if not plane_match:
            continue
        if polygons_overlap_by_centroid(zone.polygon, other.polygon):
            return other
    return None


def edge_neighbor(zone: ZonePrism, edge_start: Point2, edge_end: Point2, zones: Sequence[ZonePrism]) -> Optional[ZonePrism]:
    mx = 0.5 * (edge_start[0] + edge_end[0])
    my = 0.5 * (edge_start[1] + edge_end[1])
    dx = edge_end[0] - edge_start[0]
    dy = edge_end[1] - edge_start[1]
    length = math.hypot(dx, dy)
    if length <= TOL:
        return None
    outward = (dy / length, -dx / length)
    sample = (mx + outward[0] * 1.0e-5, my + outward[1] * 1.0e-5)
    for other in zones:
        if other.name == zone.name:
            continue
        if not (near(other.zmin, zone.zmin) and near(other.zmax, zone.zmax)):
            continue
        if point_in_polygon(sample, other.polygon):
            return other
    return None


def build_surfaces(zones: Sequence[ZonePrism]) -> List[Surface]:
    surfaces: List[Surface] = []
    global_ground = min(zone.zmin for zone in zones)
    for zone_index, zone in enumerate(sorted(zones, key=lambda z: (z.zmin, z.xmin, z.ymin, z.name)), 1):
        zone_surfaces: List[Surface] = []
        bottom_neighbor = horizontal_neighbor(zone, zones, top=False)
        top_neighbor = horizontal_neighbor(zone, zones, top=True)

        bottom_poly = list(reversed(zone.polygon))
        if bottom_neighbor is not None:
            zone_surfaces.append(make_horizontal_surface(zone, bottom_poly, zone.zmin, "Floor", "ADJ_CEILING", "Zone", bottom_neighbor.name, False, False))
        elif near(zone.zmin, global_ground):
            zone_surfaces.append(make_horizontal_surface(zone, bottom_poly, zone.zmin, "Floor", "GROUND_FLOOR", "Ground", "BOUNDARY=INPUT 1*TGROUND", False, False))
        else:
            zone_surfaces.append(make_horizontal_surface(zone, bottom_poly, zone.zmin, "Floor", "EXT_FLOOR", "Outdoors", "", True, True))

        top_poly = zone.polygon
        if top_neighbor is not None:
            zone_surfaces.append(make_horizontal_surface(zone, top_poly, zone.zmax, "Ceiling", "ADJ_CEILING", "Zone", top_neighbor.name, False, False))
        else:
            zone_surfaces.append(make_horizontal_surface(zone, top_poly, zone.zmax, "Roof", "EXT_ROOF", "Outdoors", "", True, True))

        for i, start in enumerate(zone.polygon):
            end = zone.polygon[(i + 1) % len(zone.polygon)]
            neighbor = edge_neighbor(zone, start, end, zones)
            if neighbor is None:
                zone_surfaces.append(make_vertical_surface(zone, start, end, "EXT_WALL", "Outdoors", "", True, True))
            else:
                zone_surfaces.append(make_vertical_surface(zone, start, end, "ADJ_WALL", "Zone", neighbor.name, False, False))

        for surface_index, surface in enumerate(zone_surfaces, 1):
            surface.surface_id = f"s{zone_index:02d}_{surface_index:03d}"
            surfaces.append(surface)
    return surfaces


def make_horizontal_surface(
    zone: ZonePrism,
    poly: Sequence[Point2],
    z: float,
    surface_type: str,
    construction: str,
    boundary_cond: str,
    boundary_obj: str,
    sun: bool,
    wind: bool,
) -> Surface:
    return Surface(
        surface_id="",
        surface_type=surface_type,
        construction=construction,
        zone_name=zone.name,
        boundary_cond=boundary_cond,
        boundary_obj=boundary_obj,
        sun=sun,
        wind=wind,
        vertices=[(x, y, z) for x, y in poly],
    )


def make_vertical_surface(
    zone: ZonePrism,
    start: Point2,
    end: Point2,
    construction: str,
    boundary_cond: str,
    boundary_obj: str,
    sun: bool,
    wind: bool,
) -> Surface:
    vertices = [
        (start[0], start[1], zone.zmin),
        (end[0], end[1], zone.zmin),
        (end[0], end[1], zone.zmax),
        (start[0], start[1], zone.zmax),
    ]
    return Surface(
        surface_id="",
        surface_type="Wall",
        construction=construction,
        zone_name=zone.name,
        boundary_cond=boundary_cond,
        boundary_obj=boundary_obj,
        sun=sun,
        wind=wind,
        vertices=vertices,
        edge_start=start,
        edge_end=end,
        zmin=zone.zmin,
        zmax=zone.zmax,
    )


def assign_windows(zones: Sequence[ZonePrism], surfaces: Sequence[Surface]) -> Tuple[List[Window], int]:
    exterior_by_zone: Dict[str, List[Surface]] = {}
    for surface in surfaces:
        if surface.construction == "EXT_WALL" and surface.edge_start is not None and surface.edge_end is not None:
            exterior_by_zone.setdefault(surface.zone_name, []).append(surface)

    assigned: List[Window] = []
    dropped = 0
    for zone in zones:
        index = 1
        for window in zone.windows:
            parent = find_parent_surface(window, exterior_by_zone.get(zone.name, []))
            if parent is None:
                dropped += 1
                continue
            window.final_id = f"w{zone.name[4:]}_{index:03d}" if zone.name.startswith("zone") else f"w{zone.name}_{index:03d}"
            window.parent_surface = parent.surface_id
            assigned.append(window)
            index += 1
    return assigned, dropped


def find_parent_surface(window: Window, surfaces: Sequence[Surface]) -> Optional[Surface]:
    xy_points = [(x, y) for x, y, _ in window.vertices]
    z_values = [z for _, _, z in window.vertices]
    for surface in surfaces:
        if surface.edge_start is None or surface.edge_end is None or surface.zmin is None or surface.zmax is None:
            continue
        if min(z_values) < surface.zmin - 1.0e-5 or max(z_values) > surface.zmax + 1.0e-5:
            continue
        if all(point_on_segment(point, surface.edge_start, surface.edge_end) for point in xy_points):
            return surface
    return None


def render_geometry(zones: Sequence[ZonePrism], surfaces: Sequence[Surface], windows: Sequence[Window]) -> str:
    surfaces_by_zone: Dict[str, List[Surface]] = {}
    windows_by_zone: Dict[str, List[Window]] = {}
    for surface in surfaces:
        surfaces_by_zone.setdefault(surface.zone_name, []).append(surface)
    for zone in zones:
        for window in zone.windows:
            if window.parent_surface:
                windows_by_zone.setdefault(zone.name, []).append(window)

    chunks: List[str] = []
    for zone in sorted(zones, key=lambda z: (z.zmin, z.xmin, z.ymin, z.name)):
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


def validate(
    original_zone_count: int,
    zones: Sequence[ZonePrism],
    surfaces: Sequence[Surface],
    windows: Sequence[Window],
    dropped_windows: int,
    require_same_zone_count: bool,
) -> List[str]:
    errors: List[str] = []
    if require_same_zone_count and len(zones) != original_zone_count:
        errors.append(f"Expected {original_zone_count} zones after cutting, got {len(zones)}")
    for zone in zones:
        if len(zone.polygon) < 3:
            errors.append(f"{zone.name} has fewer than three footprint vertices")
        if zone.area <= TOL:
            errors.append(f"{zone.name} has zero or negative area")
    surface_ids = [surface.surface_id for surface in surfaces]
    if len(surface_ids) != len(set(surface_ids)):
        errors.append("Duplicate BuildingSurface IDs detected")
    parent_ids = {surface.surface_id for surface in surfaces}
    window_ids = [window.final_id for window in windows]
    if len(window_ids) != len(set(window_ids)):
        errors.append("Duplicate FenestrationSurface IDs detected")
    for window in windows:
        if window.parent_surface not in parent_ids:
            errors.append(f"Window {window.final_id} points to missing parent {window.parent_surface}")
        if window.projected and window.max_x_shift > 1.0e-6:
            errors.append(f"Projected window {window.final_id} changed x-distance by {window.max_x_shift}")
    if dropped_windows:
        pass
    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cut compressed rectangular IDF zones with a slanted south facade and project south windows.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", required=True, help="Original ex*.py source")
    parser.add_argument("--template", help="IDF template; defaults to the IDF beside --source")
    parser.add_argument("--output", required=True, help="Output IDF path")
    parser.add_argument("--report", help="Optional JSON report path")
    parser.add_argument("--angle", type=float, default=60.0, help="Preset direction angle in degrees")
    parser.add_argument("--cosine", type=float, help="Use a cosine/cut ratio directly instead of --angle in normalized mode")
    parser.add_argument("--cut-ratio", type=float, help="Normalized east-end cut depth divided by model depth")
    parser.add_argument("--cut-depth", type=float, help="East-end cut depth in meters")
    parser.add_argument("--west-offset", type=float, default=0.0, help="Cut-line offset above the original southwest point")
    parser.add_argument("--line-mode", choices=("normalized", "absolute"), default="normalized", help="normalized keeps all zones practical; absolute uses tan(angle)")
    parser.add_argument("--allow-removed-zones", action="store_true", help="Allow the cut to remove zones completely")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source = Path(args.source)
    template = Path(args.template) if args.template else default_template_for_source(source)
    output = Path(args.output)

    try:
        original_zones = load_zones(source)
        cut_line = build_cut_line(args, original_zones)
        zones = apply_cut(original_zones, cut_line, args.allow_removed_zones)
        surfaces = build_surfaces(zones)
        windows, dropped_windows = assign_windows(zones, surfaces)
        errors = validate(len(original_zones), zones, surfaces, windows, dropped_windows, not args.allow_removed_zones)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 2
        geometry = render_geometry(zones, surfaces, windows)
        write_with_template(template, output, geometry)

        ratios = [zone.area / zone.original_area for zone in zones if zone.original_area > TOL]
        projected = [window for window in windows if window.projected]
        slanted_walls = [
            surface
            for surface in surfaces
            if surface.construction == "EXT_WALL"
            and surface.edge_start is not None
            and surface.edge_end is not None
            and abs(surface.edge_end[0] - surface.edge_start[0]) > TOL
            and abs(surface.edge_end[1] - surface.edge_start[1]) > TOL
        ]
        report = {
            "source": str(source),
            "template": str(template),
            "output": str(output),
            "cut_line": {
                "mode": args.line_mode,
                "description": cut_line.description,
                "x0": cut_line.x0,
                "y0": cut_line.y0,
                "slope": cut_line.slope,
            },
            "original_zones": len(original_zones),
            "final_zones": len(zones),
            "building_surfaces": len(surfaces),
            "slanted_wall_surfaces": len(slanted_walls),
            "footprint_vertex_counts": sorted({len(zone.polygon) for zone in zones}),
            "fenestration_surfaces": len(windows),
            "dropped_windows": dropped_windows,
            "projected_south_windows": len(projected),
            "max_projected_window_x_shift": max([window.max_x_shift for window in projected] or [0.0]),
            "min_area_ratio": min(ratios) if ratios else None,
            "max_area_ratio": max(ratios) if ratios else None,
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
