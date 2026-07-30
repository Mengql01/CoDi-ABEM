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
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


Point3 = Tuple[float, float, float]
Rect2 = Tuple[float, float, float, float]

TOL = 1.0e-7


def _read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text()


def _near(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def _key(v: float) -> float:
    return round(v, 7)


def _interval_overlap(a1: float, a2: float, b1: float, b2: float) -> float:
    return min(a2, b2) - max(a1, b1)


def _positive_overlap(a1: float, a2: float, b1: float, b2: float) -> bool:
    return _interval_overlap(a1, a2, b1, b2) > TOL


def _inside_open(v: float, a: float, b: float) -> bool:
    return (a + TOL) < v < (b - TOL)


def _inside_closed(v: float, a: float, b: float) -> bool:
    return (a - TOL) <= v <= (b + TOL)


def _rect_contains_point(rect: Rect2, x: float, y: float) -> bool:
    x1, x2, y1, y2 = rect
    return _inside_open(x, x1, x2) and _inside_open(y, y1, y2)


def _rects_overlap_area(a: Rect2, b: Rect2) -> bool:
    return _positive_overlap(a[0], a[1], b[0], b[1]) and _positive_overlap(a[2], a[3], b[2], b[3])


def _signed_area_xy(points: Sequence[Tuple[float, float]]) -> float:
    area = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return 0.5 * area


def _remove_collinear(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(points) <= 3:
        return points
    changed = True
    result = points[:]
    while changed and len(result) > 3:
        changed = False
        cleaned: List[Tuple[float, float]] = []
        n = len(result)
        for i, current in enumerate(result):
            prev = result[(i - 1) % n]
            nxt = result[(i + 1) % n]
            same_x = _near(prev[0], current[0]) and _near(current[0], nxt[0])
            same_y = _near(prev[1], current[1]) and _near(current[1], nxt[1])
            if same_x or same_y:
                changed = True
                continue
            cleaned.append(current)
        result = cleaned
    return result


@dataclass
class Window:
    source_id: str
    construction: str
    parent_source_id: str
    vertices: List[Point3]
    role: str
    original_zone: str
    final_id: str = ""
    parent_surface: str = ""

    def translate(self, dx: float, dy: float, dz: float = 0.0) -> None:
        self.vertices = [(x + dx, y + dy, z + dz) for x, y, z in self.vertices]


@dataclass
class Cell:
    uid: str
    role: str
    original_zone: str
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    windows: List[Window] = field(default_factory=list)
    final_zone: str = ""

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

    def translate(self, dx: float, dy: float, dz: float = 0.0) -> None:
        self.xmin += dx
        self.xmax += dx
        self.ymin += dy
        self.ymax += dy
        self.zmin += dz
        self.zmax += dz
        for window in self.windows:
            window.translate(dx, dy, dz)


@dataclass
class FinalZone:
    name: str
    cells: List[Cell]


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
    text = _read_text(path)
    tree = ast.parse(text, filename=str(path))
    assignments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "zones":
                    assignments.append(node.value)
    if not assignments:
        raise ValueError(f"No literal variable named 'zones' was found in {path}")
    zones = ast.literal_eval(assignments[-1])
    if not isinstance(zones, list):
        raise ValueError(f"The 'zones' variable in {path} is not a list")
    return zones


def _parse_window(def_item: str, role: str, zone_name: str) -> Optional[Window]:
    parts = [p.strip() for p in def_item.split(",", 3)]
    if len(parts) < 4 or parts[1] != "EXT_WINDOW1":
        return None
    vertices = [
        tuple(float(piece) for piece in match.strip("()").split(","))  # type: ignore[misc]
        for match in re.findall(r"\([^)]+\)", parts[3])
    ]
    if len(vertices) < 3:
        raise ValueError(f"Window {parts[0]} in {zone_name} has fewer than three vertices")
    return Window(
        source_id=parts[0],
        construction=parts[1],
        parent_source_id=parts[2],
        vertices=vertices,  # type: ignore[arg-type]
        role=role,
        original_zone=zone_name,
    )


def _rotate_point(point: Point3, orientation: str) -> Point3:
    x, y, z = point
    if orientation == "ew":
        return (x, y, z)
    if orientation == "ns":
        return (-y, x, z)
    raise ValueError(f"Unknown orientation: {orientation}")


def load_instance(source: Path, role: str, orientation: str) -> List[Cell]:
    raw_zones = extract_zones_from_python(source)
    rotated_zone_vertices: Dict[str, List[Point3]] = {}
    rotated_windows: Dict[str, List[Window]] = {}
    all_points: List[Point3] = []

    for zone_tuple in raw_zones:
        if len(zone_tuple) < 2:
            raise ValueError(f"Bad zone tuple in {source}: {zone_tuple!r}")
        zone_name = str(zone_tuple[0])
        vertices = [_rotate_point(tuple(map(float, p)), orientation) for p in zone_tuple[1]]
        if len(vertices) != 8:
            raise ValueError(f"{zone_name} in {source} does not have eight cuboid vertices")
        rotated_zone_vertices[zone_name] = vertices
        all_points.extend(vertices)

        windows: List[Window] = []
        for def_item in zone_tuple[2:]:
            if not isinstance(def_item, str):
                continue
            window = _parse_window(def_item, role, zone_name)
            if window is not None:
                window.vertices = [_rotate_point(v, orientation) for v in window.vertices]
                all_points.extend(window.vertices)
                windows.append(window)
        rotated_windows[zone_name] = windows

    min_x = min(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    min_z = min(p[2] for p in all_points)
    dx = -min_x
    dy = -min_y
    dz = -min_z

    cells: List[Cell] = []
    for zone_name, vertices in rotated_zone_vertices.items():
        normalized = [(x + dx, y + dy, z + dz) for x, y, z in vertices]
        xs = [p[0] for p in normalized]
        ys = [p[1] for p in normalized]
        zs = [p[2] for p in normalized]
        for window in rotated_windows[zone_name]:
            window.translate(dx, dy, dz)
        cell = Cell(
            uid=f"{role}:{zone_name}",
            role=role,
            original_zone=zone_name,
            xmin=min(xs),
            xmax=max(xs),
            ymin=min(ys),
            ymax=max(ys),
            zmin=min(zs),
            zmax=max(zs),
            windows=rotated_windows[zone_name],
        )
        cells.append(cell)
    return cells


def _floor_groups(cells: Sequence[Cell], axis: str) -> List[List[Cell]]:
    groups: Dict[Tuple[float, float], List[Cell]] = {}
    for cell in cells:
        groups.setdefault((_key(cell.zmin), _key(cell.zmax)), []).append(cell)
    result: List[List[Cell]] = []
    for _, floor_cells in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        if axis == "x":
            floor_cells.sort(key=lambda c: (c.cx, c.cy, c.original_zone))
        else:
            floor_cells.sort(key=lambda c: (c.cy, c.cx, c.original_zone))
        result.append(floor_cells)
    return result


def _role_axis(orientation: str) -> str:
    return "x" if orientation == "ew" else "y"


def _pick_middle(cells: Sequence[Cell]) -> Cell:
    return cells[len(cells) // 2]


def _pick_end(cells: Sequence[Cell], which: str) -> Cell:
    return cells[0] if which == "start" else cells[-1]


def auto_t_merges(
    main_cells: Sequence[Cell],
    branch_cells: Sequence[Cell],
    main_orientation: str,
    branch_orientation: str,
    branch_end: str,
) -> List[Tuple[str, str]]:
    main_floors = _floor_groups(main_cells, _role_axis(main_orientation))
    branch_floors = _floor_groups(branch_cells, _role_axis(branch_orientation))
    if len(main_floors) != len(branch_floors):
        raise ValueError("T auto-merge requires the main and branch models to have the same floor count")
    merges = []
    for main_floor, branch_floor in zip(main_floors, branch_floors):
        merges.append((_pick_middle(main_floor).uid, _pick_end(branch_floor, branch_end).uid))
    return merges


def auto_h_merges(
    left_cells: Sequence[Cell],
    connector_cells: Sequence[Cell],
    right_cells: Sequence[Cell],
    side_orientation: str,
    connector_orientation: str,
) -> List[Tuple[str, str]]:
    left_floors = _floor_groups(left_cells, _role_axis(side_orientation))
    connector_floors = _floor_groups(connector_cells, _role_axis(connector_orientation))
    right_floors = _floor_groups(right_cells, _role_axis(side_orientation))
    if not (len(left_floors) == len(connector_floors) == len(right_floors)):
        raise ValueError("H auto-merge requires all three models to have the same floor count")
    merges = []
    for left_floor, connector_floor, right_floor in zip(left_floors, connector_floors, right_floors):
        connector_start = _pick_end(connector_floor, "start")
        connector_end = _pick_end(connector_floor, "end")
        merges.append((_pick_middle(left_floor).uid, connector_start.uid))
        merges.append((connector_end.uid, _pick_middle(right_floor).uid))
    return merges


def _zone_number(name: str) -> Optional[int]:
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else None


def resolve_zone_ref(ref: str, cells_by_uid: Dict[str, Cell]) -> str:
    if ":" not in ref:
        raise ValueError(f"Merge reference must be role:zone, got {ref!r}")
    role, token = [part.strip() for part in ref.split(":", 1)]
    exact = f"{role}:{token}"
    if exact in cells_by_uid:
        return exact

    numeric = int(token) if token.isdigit() else _zone_number(token)
    if numeric is not None:
        matches = [
            uid
            for uid, cell in cells_by_uid.items()
            if cell.role == role and _zone_number(cell.original_zone) == numeric
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"Merge reference {ref!r} is ambiguous: {matches}")

    role_matches = sorted(uid for uid, cell in cells_by_uid.items() if cell.role == role)
    raise ValueError(f"Could not resolve merge reference {ref!r}. Available for role {role}: {role_matches}")


def parse_merge_specs(specs: Sequence[str], cells_by_uid: Dict[str, Cell]) -> List[Tuple[str, str]]:
    merges = []
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"Merge spec must look like role:zone=role:zone, got {spec!r}")
        left, right = [part.strip() for part in spec.split("=", 1)]
        merges.append((resolve_zone_ref(left, cells_by_uid), resolve_zone_ref(right, cells_by_uid)))
    return merges


def _cell_pair_for_roles(
    merges: Sequence[Tuple[str, str]],
    cells_by_uid: Dict[str, Cell],
    role_a: str,
    role_b: str,
) -> Tuple[Cell, Cell]:
    for left, right in merges:
        c1 = cells_by_uid[left]
        c2 = cells_by_uid[right]
        if c1.role == role_a and c2.role == role_b:
            return c1, c2
        if c1.role == role_b and c2.role == role_a:
            return c2, c1
    raise ValueError(f"No merge pair found between roles {role_a!r} and {role_b!r}")


def translate_cells(cells: Sequence[Cell], dx: float, dy: float, dz: float = 0.0) -> None:
    for cell in cells:
        cell.translate(dx, dy, dz)


def place_branch_for_t(main_cell: Cell, branch_cell: Cell, branch_cells: Sequence[Cell], attach_side: str) -> None:
    if attach_side == "east":
        dx = main_cell.xmax - branch_cell.xmin
        dy = main_cell.cy - branch_cell.cy
    elif attach_side == "west":
        dx = main_cell.xmin - branch_cell.xmax
        dy = main_cell.cy - branch_cell.cy
    elif attach_side == "north":
        dx = main_cell.cx - branch_cell.cx
        dy = main_cell.ymax - branch_cell.ymin
    elif attach_side == "south":
        dx = main_cell.cx - branch_cell.cx
        dy = main_cell.ymin - branch_cell.ymax
    else:
        raise ValueError(f"Unknown attach side: {attach_side}")
    dz = main_cell.zmin - branch_cell.zmin
    translate_cells(branch_cells, dx, dy, dz)


def place_h_components(
    left_cell: Cell,
    connector_left_cell: Cell,
    connector_cells: Sequence[Cell],
    connector_right_cell: Cell,
    right_cell: Cell,
    right_cells: Sequence[Cell],
) -> None:
    dx = left_cell.xmax - connector_left_cell.xmin
    dy = left_cell.cy - connector_left_cell.cy
    dz = left_cell.zmin - connector_left_cell.zmin
    translate_cells(connector_cells, dx, dy, dz)

    dx = connector_right_cell.xmax - right_cell.xmin
    dy = connector_right_cell.cy - right_cell.cy
    dz = connector_right_cell.zmin - right_cell.zmin
    translate_cells(right_cells, dx, dy, dz)


def face_touching(a: Cell, b: Cell) -> bool:
    x_touch = (_near(a.xmax, b.xmin) or _near(a.xmin, b.xmax)) and _positive_overlap(a.ymin, a.ymax, b.ymin, b.ymax) and _positive_overlap(a.zmin, a.zmax, b.zmin, b.zmax)
    y_touch = (_near(a.ymax, b.ymin) or _near(a.ymin, b.ymax)) and _positive_overlap(a.xmin, a.xmax, b.xmin, b.xmax) and _positive_overlap(a.zmin, a.zmax, b.zmin, b.zmax)
    z_touch = (_near(a.zmax, b.zmin) or _near(a.zmin, b.zmax)) and _positive_overlap(a.xmin, a.xmax, b.xmin, b.xmax) and _positive_overlap(a.ymin, a.ymax, b.ymin, b.ymax)
    return x_touch or y_touch or z_touch


def positive_volume_overlap(a: Cell, b: Cell) -> bool:
    return (
        _positive_overlap(a.xmin, a.xmax, b.xmin, b.xmax)
        and _positive_overlap(a.ymin, a.ymax, b.ymin, b.ymax)
        and _positive_overlap(a.zmin, a.zmax, b.zmin, b.zmax)
    )


def assign_final_zones(cells: Sequence[Cell], merges: Sequence[Tuple[str, str]]) -> List[FinalZone]:
    uf = UnionFind(cell.uid for cell in cells)
    for a, b in merges:
        uf.union(a, b)

    grouped: Dict[str, List[Cell]] = {}
    for cell in cells:
        grouped.setdefault(uf.find(cell.uid), []).append(cell)

    groups = list(grouped.values())
    groups.sort(key=lambda group: (min(c.zmin for c in group), min(c.xmin for c in group), min(c.ymin for c in group), min(c.original_zone for c in group)))
    width = max(2, len(str(len(groups))))
    final_zones: List[FinalZone] = []
    for index, group in enumerate(groups, 1):
        name = f"zone{index:0{width}d}"
        for cell in group:
            cell.final_zone = name
        final_zones.append(FinalZone(name=name, cells=sorted(group, key=lambda c: (c.zmin, c.xmin, c.ymin, c.uid))))
    return final_zones


def rects_to_polygons(rects: Sequence[Rect2]) -> List[List[Tuple[float, float]]]:
    if not rects:
        return []
    xs = sorted({_key(v) for rect in rects for v in (rect[0], rect[1])})
    ys = sorted({_key(v) for rect in rects for v in (rect[2], rect[3])})
    x_index = {v: i for i, v in enumerate(xs)}
    y_index = {v: i for i, v in enumerate(ys)}
    filled: Set[Tuple[int, int]] = set()
    for rect in rects:
        x1, x2, y1, y2 = (_key(rect[0]), _key(rect[1]), _key(rect[2]), _key(rect[3]))
        ix1, ix2 = x_index[x1], x_index[x2]
        iy1, iy2 = y_index[y1], y_index[y2]
        for ix in range(ix1, ix2):
            for iy in range(iy1, iy2):
                filled.add((ix, iy))

    edges: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for ix, iy in filled:
        if (ix, iy - 1) not in filled:
            edges.append(((ix, iy), (ix + 1, iy)))
        if (ix + 1, iy) not in filled:
            edges.append(((ix + 1, iy), (ix + 1, iy + 1)))
        if (ix, iy + 1) not in filled:
            edges.append(((ix + 1, iy + 1), (ix, iy + 1)))
        if (ix - 1, iy) not in filled:
            edges.append(((ix, iy + 1), (ix, iy)))

    outgoing: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for start, end in edges:
        outgoing.setdefault(start, []).append(end)

    unused = set(edges)
    loops: List[List[Tuple[float, float]]] = []
    while unused:
        start, end = next(iter(unused))
        unused.remove((start, end))
        loop = [start]
        current = end
        while current != start:
            loop.append(current)
            candidates = outgoing.get(current, [])
            next_point = None
            for candidate in candidates:
                edge = (current, candidate)
                if edge in unused:
                    next_point = candidate
                    unused.remove(edge)
                    break
            if next_point is None:
                raise ValueError("Could not trace an orthogonal polygon boundary")
            current = next_point
        coords = [(xs[ix], ys[iy]) for ix, iy in loop]
        coords = _remove_collinear(coords)
        if len(coords) >= 3:
            loops.append(coords)
    return loops


def _horizontal_neighbor(cell: Cell, x: float, y: float, z: float, top: bool, all_cells: Sequence[Cell]) -> Optional[Cell]:
    for candidate in all_cells:
        if top:
            touches_plane = _near(candidate.zmin, z)
        else:
            touches_plane = _near(candidate.zmax, z)
        if not touches_plane:
            continue
        if _inside_open(x, candidate.xmin, candidate.xmax) and _inside_open(y, candidate.ymin, candidate.ymax):
            return candidate
    return None


def _horizontal_rect_pieces(cell: Cell, top: bool, all_cells: Sequence[Cell]) -> List[Tuple[Tuple[str, str, str, str, bool, bool], Rect2]]:
    z = cell.zmax if top else cell.zmin
    base_rect = cell.rect
    xs = [cell.xmin, cell.xmax]
    ys = [cell.ymin, cell.ymax]
    for other in all_cells:
        if other.uid == cell.uid:
            continue
        plane_match = _near(other.zmin, z) if top else _near(other.zmax, z)
        if not plane_match or not _rects_overlap_area(base_rect, other.rect):
            continue
        xs.extend([max(cell.xmin, other.xmin), min(cell.xmax, other.xmax)])
        ys.extend([max(cell.ymin, other.ymin), min(cell.ymax, other.ymax)])
    xs = sorted({_key(v) for v in xs})
    ys = sorted({_key(v) for v in ys})

    pieces: List[Tuple[Tuple[str, str, str, str, bool, bool], Rect2]] = []
    global_ground = min(c.zmin for c in all_cells)
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            x1, x2 = xs[ix], xs[ix + 1]
            y1, y2 = ys[iy], ys[iy + 1]
            if x2 - x1 <= TOL or y2 - y1 <= TOL:
                continue
            cx, cy = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
            if not _rect_contains_point(base_rect, cx, cy):
                continue
            neighbor = _horizontal_neighbor(cell, cx, cy, z, top, all_cells)
            if neighbor is not None and neighbor.final_zone == cell.final_zone:
                continue
            if neighbor is not None:
                surface_type = "Ceiling" if top else "Floor"
                key = (surface_type, "ADJ_CEILING", "Zone", neighbor.final_zone, False, False)
            elif top:
                key = ("Roof", "EXT_ROOF", "Outdoors", "", True, True)
            elif _near(z, global_ground):
                key = ("Floor", "GROUND_FLOOR", "Ground", "BOUNDARY=INPUT 1*TGROUND", False, False)
            else:
                key = ("Floor", "EXT_FLOOR", "Outdoors", "", True, True)
            pieces.append((key, (x1, x2, y1, y2)))
    return pieces


def _make_horizontal_surfaces(zone: FinalZone, all_cells: Sequence[Cell]) -> List[Surface]:
    grouped: Dict[Tuple[float, Tuple[str, str, str, str, bool, bool], bool], List[Rect2]] = {}
    for cell in zone.cells:
        for top in (False, True):
            z = cell.zmax if top else cell.zmin
            for key, rect in _horizontal_rect_pieces(cell, top, all_cells):
                grouped.setdefault((_key(z), key, top), []).append(rect)

    surfaces: List[Surface] = []
    for (z, key, top), rects in grouped.items():
        surface_type, construction, boundary_cond, boundary_obj, sun, wind = key
        for polygon in rects_to_polygons(rects):
            if top and _signed_area_xy(polygon) < 0:
                polygon = list(reversed(polygon))
            if not top and _signed_area_xy(polygon) > 0:
                polygon = list(reversed(polygon))
            vertices = [(x, y, z) for x, y in polygon]
            surfaces.append(
                Surface(
                    surface_id="",
                    surface_type=surface_type,
                    construction=construction,
                    zone_name=zone.name,
                    boundary_cond=boundary_cond,
                    boundary_obj=boundary_obj,
                    sun=sun,
                    wind=wind,
                    vertices=vertices,
                )
            )
    return surfaces


def _vertical_neighbor(cell: Cell, side: str, a_mid: float, z_mid: float, all_cells: Sequence[Cell]) -> Optional[Cell]:
    for candidate in all_cells:
        if candidate.uid == cell.uid:
            continue
        if not _inside_open(z_mid, candidate.zmin, candidate.zmax):
            continue
        if side == "east":
            if _near(candidate.xmin, cell.xmax) and _inside_open(a_mid, candidate.ymin, candidate.ymax):
                return candidate
        elif side == "west":
            if _near(candidate.xmax, cell.xmin) and _inside_open(a_mid, candidate.ymin, candidate.ymax):
                return candidate
        elif side == "north":
            if _near(candidate.ymin, cell.ymax) and _inside_open(a_mid, candidate.xmin, candidate.xmax):
                return candidate
        elif side == "south":
            if _near(candidate.ymax, cell.ymin) and _inside_open(a_mid, candidate.xmin, candidate.xmax):
                return candidate
    return None


def _vertical_breaks(cell: Cell, side: str, all_cells: Sequence[Cell]) -> List[float]:
    if side in ("east", "west"):
        a1, a2 = cell.ymin, cell.ymax
    else:
        a1, a2 = cell.xmin, cell.xmax
    breaks = [a1, a2]
    for other in all_cells:
        if other.uid == cell.uid:
            continue
        if not _positive_overlap(cell.zmin, cell.zmax, other.zmin, other.zmax):
            continue
        if side == "east" and not _near(other.xmin, cell.xmax):
            continue
        if side == "west" and not _near(other.xmax, cell.xmin):
            continue
        if side == "north" and not _near(other.ymin, cell.ymax):
            continue
        if side == "south" and not _near(other.ymax, cell.ymin):
            continue
        if side in ("east", "west"):
            if _positive_overlap(a1, a2, other.ymin, other.ymax):
                breaks.extend([max(a1, other.ymin), min(a2, other.ymax)])
        else:
            if _positive_overlap(a1, a2, other.xmin, other.xmax):
                breaks.extend([max(a1, other.xmin), min(a2, other.xmax)])
    return sorted({_key(v) for v in breaks})


def _wall_vertices(cell: Cell, side: str, a1: float, a2: float) -> Tuple[List[Point3], str, float, Tuple[float, float]]:
    z1, z2 = cell.zmin, cell.zmax
    if side == "east":
        x = cell.xmax
        return ([(x, a2, z2), (x, a1, z2), (x, a1, z1), (x, a2, z1)], "x", x, (a1, a2))
    if side == "west":
        x = cell.xmin
        return ([(x, a2, z1), (x, a1, z1), (x, a1, z2), (x, a2, z2)], "x", x, (a1, a2))
    if side == "north":
        y = cell.ymax
        return ([(a2, y, z1), (a1, y, z1), (a1, y, z2), (a2, y, z2)], "y", y, (a1, a2))
    if side == "south":
        y = cell.ymin
        return ([(a1, y, z1), (a2, y, z1), (a2, y, z2), (a1, y, z2)], "y", y, (a1, a2))
    raise ValueError(f"Unknown side: {side}")


def _make_vertical_surfaces(zone: FinalZone, all_cells: Sequence[Cell]) -> List[Surface]:
    surfaces: List[Surface] = []
    for cell in zone.cells:
        for side in ("east", "west", "north", "south"):
            breaks = _vertical_breaks(cell, side, all_cells)
            for a1, a2 in zip(breaks, breaks[1:]):
                if a2 - a1 <= TOL:
                    continue
                neighbor = _vertical_neighbor(cell, side, 0.5 * (a1 + a2), cell.cz, all_cells)
                if neighbor is not None and neighbor.final_zone == cell.final_zone:
                    continue
                if neighbor is None:
                    construction = "EXT_WALL"
                    boundary_cond = "Outdoors"
                    boundary_obj = ""
                    sun = True
                    wind = True
                else:
                    construction = "ADJ_WALL"
                    boundary_cond = "Zone"
                    boundary_obj = neighbor.final_zone
                    sun = False
                    wind = False
                vertices, plane, constant, span_a = _wall_vertices(cell, side, a1, a2)
                surfaces.append(
                    Surface(
                        surface_id="",
                        surface_type="Wall",
                        construction=construction,
                        zone_name=zone.name,
                        boundary_cond=boundary_cond,
                        boundary_obj=boundary_obj,
                        sun=sun,
                        wind=wind,
                        vertices=vertices,
                        plane=plane,
                        constant=constant,
                        span_a=span_a,
                        span_z=(cell.zmin, cell.zmax),
                    )
                )
    return surfaces


def build_surfaces(final_zones: Sequence[FinalZone], all_cells: Sequence[Cell]) -> List[Surface]:
    surfaces: List[Surface] = []
    for zone_index, zone in enumerate(final_zones, 1):
        zone_surfaces = _make_horizontal_surfaces(zone, all_cells) + _make_vertical_surfaces(zone, all_cells)
        for surface_index, surface in enumerate(zone_surfaces, 1):
            surface.surface_id = f"s{zone_index:02d}_{surface_index:03d}"
            surfaces.append(surface)
    return surfaces


def _window_plane(window: Window) -> Optional[Tuple[str, float, Tuple[float, float], Tuple[float, float]]]:
    xs = [v[0] for v in window.vertices]
    ys = [v[1] for v in window.vertices]
    zs = [v[2] for v in window.vertices]
    if max(xs) - min(xs) <= TOL:
        return ("x", sum(xs) / len(xs), (min(ys), max(ys)), (min(zs), max(zs)))
    if max(ys) - min(ys) <= TOL:
        return ("y", sum(ys) / len(ys), (min(xs), max(xs)), (min(zs), max(zs)))
    return None


def assign_windows(final_zones: Sequence[FinalZone], surfaces: Sequence[Surface]) -> Tuple[List[Window], int]:
    exterior_by_zone: Dict[str, List[Surface]] = {}
    for surface in surfaces:
        if surface.construction == "EXT_WALL" and surface.plane is not None:
            exterior_by_zone.setdefault(surface.zone_name, []).append(surface)

    assigned: List[Window] = []
    dropped = 0
    for zone in final_zones:
        window_index = 1
        for cell in zone.cells:
            for window in cell.windows:
                plane = _window_plane(window)
                if plane is None:
                    dropped += 1
                    continue
                axis, constant, span_a, span_z = plane
                parent: Optional[Surface] = None
                for surface in exterior_by_zone.get(zone.name, []):
                    if surface.plane != axis or surface.constant is None or surface.span_a is None or surface.span_z is None:
                        continue
                    if not _near(surface.constant, constant):
                        continue
                    if not (_inside_closed(span_a[0], surface.span_a[0], surface.span_a[1]) and _inside_closed(span_a[1], surface.span_a[0], surface.span_a[1])):
                        continue
                    if not (_inside_closed(span_z[0], surface.span_z[0], surface.span_z[1]) and _inside_closed(span_z[1], surface.span_z[0], surface.span_z[1])):
                        continue
                    parent = surface
                    break
                if parent is None:
                    dropped += 1
                    continue
                window.final_id = f"w{zone.name[4:]}_{window_index:03d}"
                window.parent_surface = parent.surface_id
                assigned.append(window)
                window_index += 1
    return assigned, dropped


def _format_number(value: float) -> str:
    if abs(value) < 0.5e-12:
        value = 0.0
    return f"{value:.12f}"


def render_idf_geometry(final_zones: Sequence[FinalZone], surfaces: Sequence[Surface], windows: Sequence[Window]) -> str:
    surfaces_by_zone: Dict[str, List[Surface]] = {}
    windows_by_zone: Dict[str, List[Window]] = {}
    for surface in surfaces:
        surfaces_by_zone.setdefault(surface.zone_name, []).append(surface)
    for window in windows:
        for zone in final_zones:
            if any(cell.uid == f"{window.role}:{window.original_zone}" for cell in zone.cells):
                windows_by_zone.setdefault(zone.name, []).append(window)
                break

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
            chunks.append(_render_surface(surface))
        for window in windows_by_zone.get(zone.name, []):
            chunks.append(_render_window(window))
    return "\n".join(chunks).rstrip() + "\n"


def _render_surface(surface: Surface) -> str:
    vertex_lines = []
    for index, (x, y, z) in enumerate(surface.vertices, 1):
        terminator = ";" if index == len(surface.vertices) else ","
        vertex_lines.append(f"    {_format_number(x)},\n    {_format_number(y)},\n    {_format_number(z)}{terminator}")
    boundary_obj = surface.boundary_obj if surface.boundary_obj else ""
    return f"""  BuildingSurface:Detailed,
    {surface.surface_id},
    {surface.surface_type},
    {surface.construction},
    {surface.zone_name},
    {surface.boundary_cond},
    {boundary_obj},
    {'SunExposed' if surface.sun else 'NoSun'},
    {'WindExposed' if surface.wind else 'NoWind'},
    ,
    {len(surface.vertices)},
{chr(10).join(vertex_lines)}
"""


def _render_window(window: Window) -> str:
    vertex_lines = []
    for index, (x, y, z) in enumerate(window.vertices, 1):
        terminator = ";" if index == len(window.vertices) else ","
        vertex_lines.append(f"    {_format_number(x)},\n    {_format_number(y)},\n    {_format_number(z)}{terminator}")
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


def write_with_template(template: Path, output: Path, geometry_text: str) -> None:
    template_text = _read_text(template)
    match = re.search(r"(?im)^\s*Zone\s*,\s*$", template_text)
    if match:
        prefix = template_text[: match.start()].rstrip()
    else:
        prefix = template_text.rstrip()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prefix + "\n\n" + geometry_text.rstrip() + "\n", encoding="utf-8")


def validate_model(
    final_zones: Sequence[FinalZone],
    all_cells: Sequence[Cell],
    merges: Sequence[Tuple[str, str]],
    cells_by_uid: Dict[str, Cell],
    surfaces: Sequence[Surface],
    windows: Sequence[Window],
) -> List[str]:
    errors: List[str] = []
    for left, right in merges:
        if not face_touching(cells_by_uid[left], cells_by_uid[right]):
            errors.append(f"Merged cells do not share a face: {left} and {right}")

    for i, a in enumerate(all_cells):
        for b in all_cells[i + 1 :]:
            if positive_volume_overlap(a, b):
                errors.append(f"Cells overlap with positive volume: {a.uid} and {b.uid}")

    for zone in final_zones:
        if not _zone_cells_connected(zone.cells):
            errors.append(f"Final zone {zone.name} is not face-connected")

    surface_ids = [surface.surface_id for surface in surfaces]
    if len(surface_ids) != len(set(surface_ids)):
        errors.append("Duplicate BuildingSurface IDs detected")
    for surface in surfaces:
        if len(surface.vertices) < 3:
            errors.append(f"Surface {surface.surface_id} has fewer than three vertices")

    parent_ids = {surface.surface_id for surface in surfaces}
    window_ids = [window.final_id for window in windows]
    if len(window_ids) != len(set(window_ids)):
        errors.append("Duplicate FenestrationSurface IDs detected")
    for window in windows:
        if window.parent_surface not in parent_ids:
            errors.append(f"Window {window.final_id} points to missing parent {window.parent_surface}")
        if len(window.vertices) < 3:
            errors.append(f"Window {window.final_id} has fewer than three vertices")
    return errors


def _zone_cells_connected(cells: Sequence[Cell]) -> bool:
    if not cells:
        return False
    seen = {cells[0].uid}
    changed = True
    while changed:
        changed = False
        for cell in cells:
            if cell.uid in seen:
                continue
            if any(face_touching(cell, other) for other in cells if other.uid in seen):
                seen.add(cell.uid)
                changed = True
    return len(seen) == len(cells)


def build_complex_model(args: argparse.Namespace) -> Tuple[List[FinalZone], List[Cell], List[Tuple[str, str]], List[Surface], List[Window], int]:
    source = Path(args.source)
    main_source = Path(args.main_source) if args.main_source else source
    branch_source = Path(args.branch_source) if args.branch_source else source
    left_source = Path(args.left_source) if args.left_source else source
    connector_source = Path(args.connector_source) if args.connector_source else source
    right_source = Path(args.right_source) if args.right_source else source

    if args.shape == "T":
        main_cells = load_instance(main_source, "main", args.main_orientation)
        branch_cells = load_instance(branch_source, "branch", args.branch_orientation)
        all_cells = list(main_cells) + list(branch_cells)
        cells_by_uid = {cell.uid: cell for cell in all_cells}
        merges = parse_merge_specs(args.merge, cells_by_uid) if args.merge else auto_t_merges(main_cells, branch_cells, args.main_orientation, args.branch_orientation, args.branch_end)
        main_cell, branch_cell = _cell_pair_for_roles(merges, cells_by_uid, "main", "branch")
        place_branch_for_t(main_cell, branch_cell, branch_cells, args.attach_side)
    else:
        left_cells = load_instance(left_source, "left", args.side_orientation)
        connector_cells = load_instance(connector_source, "connector", args.connector_orientation)
        right_cells = load_instance(right_source, "right", args.side_orientation)
        all_cells = list(left_cells) + list(connector_cells) + list(right_cells)
        cells_by_uid = {cell.uid: cell for cell in all_cells}
        merges = parse_merge_specs(args.merge, cells_by_uid) if args.merge else auto_h_merges(left_cells, connector_cells, right_cells, args.side_orientation, args.connector_orientation)
        left_cell, connector_left_cell = _cell_pair_for_roles(merges, cells_by_uid, "left", "connector")
        connector_right_cell, right_cell = _cell_pair_for_roles(merges, cells_by_uid, "connector", "right")
        place_h_components(left_cell, connector_left_cell, connector_cells, connector_right_cell, right_cell, right_cells)

    cells_by_uid = {cell.uid: cell for cell in all_cells}
    final_zones = assign_final_zones(all_cells, merges)
    surfaces = build_surfaces(final_zones, all_cells)
    windows, dropped_windows = assign_windows(final_zones, surfaces)
    return final_zones, all_cells, merges, surfaces, windows, dropped_windows


def default_template_for_source(source: Path) -> Path:
    candidate = source.parent / "Empty_Zone_Template_01_06.idf"
    if candidate.exists():
        return candidate
    matches = list(source.parent.glob("*.idf"))
    if not matches:
        raise FileNotFoundError(f"No IDF template was found next to {source}")
    return matches[0]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine compressed IDF zone samples into T-shaped or H-shaped buildings.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--shape", choices=("T", "H"), required=True, help="Target complex-building shape")
    parser.add_argument("--source", required=True, help="Default ex*.py source used for every component")
    parser.add_argument("--template", help="IDF template. If omitted, the IDF beside --source is used")
    parser.add_argument("--output", required=True, help="Output IDF path")
    parser.add_argument("--report", help="Optional JSON validation report path")
    parser.add_argument("--merge", action="append", default=[], help="Manual merge pair, e.g. main:3=branch:1 or left:zone03=connector:zone01")

    parser.add_argument("--main-source", help="T shape: source for the main component")
    parser.add_argument("--branch-source", help="T shape: source for the branch component")
    parser.add_argument("--left-source", help="H shape: source for the left component")
    parser.add_argument("--connector-source", help="H shape: source for the connector component")
    parser.add_argument("--right-source", help="H shape: source for the right component")

    parser.add_argument("--main-orientation", choices=("ew", "ns"), default="ns", help="T shape main component orientation")
    parser.add_argument("--branch-orientation", choices=("ew", "ns"), default="ew", help="T shape branch component orientation")
    parser.add_argument("--side-orientation", choices=("ew", "ns"), default="ns", help="H shape side-bar orientation")
    parser.add_argument("--connector-orientation", choices=("ew", "ns"), default="ew", help="H shape connector orientation")
    parser.add_argument("--attach-side", choices=("east", "west", "north", "south"), default="east", help="T shape: side of main component used for attachment")
    parser.add_argument("--branch-end", choices=("start", "end"), default="start", help="T auto-merge: branch end selected for merging")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source = Path(args.source)
    template = Path(args.template) if args.template else default_template_for_source(source)
    output = Path(args.output)

    try:
        final_zones, all_cells, merges, surfaces, windows, dropped_windows = build_complex_model(args)
        cells_by_uid = {cell.uid: cell for cell in all_cells}
        errors = validate_model(final_zones, all_cells, merges, cells_by_uid, surfaces, windows)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 2
        geometry = render_idf_geometry(final_zones, surfaces, windows)
        write_with_template(template, output, geometry)

        report = {
            "shape": args.shape,
            "source": str(source),
            "template": str(template),
            "output": str(output),
            "input_cells": len(all_cells),
            "merge_pairs": len(merges),
            "final_zones": len(final_zones),
            "building_surfaces": len(surfaces),
            "fenestration_surfaces": len(windows),
            "dropped_windows": dropped_windows,
            "merges": [{"left": a, "right": b} for a, b in merges],
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
