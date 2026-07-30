#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple


Point3 = Tuple[float, float, float]
TOL = 1.0e-7

STYLES = ("shed-x", "shed-y", "gable-x", "gable-y", "local-gable")


@dataclass
class Surface:
    fields: List[str]
    vertices: List[Point3]


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def strip_comments(text: str) -> str:
    return "\n".join(line.split("!")[0] for line in text.splitlines())


def split_idf_objects(text: str) -> List[List[str]]:
    objects: List[List[str]] = []
    for chunk in strip_comments(text).split(";"):
        if not chunk.strip():
            continue
        fields = [field.strip() for field in chunk.replace("\n", " ").split(",")]
        if fields and fields[0]:
            objects.append(fields)
    return objects


def vertices_from_fields(fields: Sequence[str], vertex_count_index: int) -> List[Point3]:
    count = int(float(fields[vertex_count_index]))
    values = [float(value) for value in fields[vertex_count_index + 1 : vertex_count_index + 1 + count * 3]]
    return [tuple(values[index : index + 3]) for index in range(0, len(values), 3)]  # type: ignore[list-item]


def format_number(value: float) -> str:
    if abs(value) < 0.5e-12:
        value = 0.0
    return f"{value:.12f}"


def geometry_prefix(text: str) -> str:
    match = re.search(r"(?im)^\s*Zone\s*,\s*$", text)
    return text[: match.start()].rstrip() if match else ""


def parse_geometry(text: str) -> Tuple[str, List[List[str]], List[Surface]]:
    prefix = geometry_prefix(text)
    geometry = text[len(prefix) :] if prefix else text
    objects = split_idf_objects(geometry)
    surfaces: List[Surface] = []
    for fields in objects:
        if fields[0].lower() == "buildingsurface:detailed":
            surfaces.append(Surface(fields=fields, vertices=vertices_from_fields(fields, 10)))
    return prefix, objects, surfaces


def top_vertex_coordinates(surfaces: Sequence[Surface]) -> Tuple[float, List[Point3]]:
    roof_vertices = [
        vertex
        for surface in surfaces
        if surface.fields[2].lower() == "roof" or surface.fields[3].upper() == "EXT_ROOF"
        for vertex in surface.vertices
    ]
    if not roof_vertices:
        raise ValueError("No roof surfaces were found in the input IDF")
    top_z = max(z for _, _, z in roof_vertices)
    top_vertices = [vertex for surface in surfaces for vertex in surface.vertices if abs(vertex[2] - top_z) <= TOL]
    return top_z, top_vertices


def nearest_existing_coordinate(values: Sequence[float], target: float) -> float:
    unique = sorted({round(value, 7) for value in values})
    return min(unique, key=lambda value: abs(value - target))


def height_delta(
    x: float,
    y: float,
    style: str,
    rise: float,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    ridge_x: float,
    ridge_y: float,
) -> float:
    width = max(xmax - xmin, TOL)
    depth = max(ymax - ymin, TOL)
    if style == "shed-x":
        return rise * (x - xmin) / width
    if style == "shed-y":
        return rise * (y - ymin) / depth
    if style == "gable-x":
        half = max(max(ridge_x - xmin, xmax - ridge_x), TOL)
        return rise * max(0.0, 1.0 - abs(x - ridge_x) / half)
    if style == "gable-y":
        half = max(max(ridge_y - ymin, ymax - ridge_y), TOL)
        return rise * max(0.0, 1.0 - abs(y - ridge_y) / half)
    raise ValueError(f"Unsupported roof style: {style}")


def lift_roof(objects: Sequence[List[str]], surfaces: Sequence[Surface], style: str, rise: float) -> Tuple[List[List[str]], dict]:
    if style == "local-gable":
        return lift_local_gable(objects, rise)

    top_z, top_vertices = top_vertex_coordinates(surfaces)
    xs = [x for x, _, _ in top_vertices]
    ys = [y for _, y, _ in top_vertices]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    ridge_x = nearest_existing_coordinate(xs, 0.5 * (xmin + xmax))
    ridge_y = nearest_existing_coordinate(ys, 0.5 * (ymin + ymax))

    modified_top_vertices = 0
    new_objects: List[List[str]] = []
    for fields in objects:
        if fields[0].lower() != "buildingsurface:detailed":
            new_objects.append(list(fields))
            continue
        vertices = vertices_from_fields(fields, 10)
        new_vertices: List[Point3] = []
        changed = False
        for x, y, z in vertices:
            if abs(z - top_z) <= TOL:
                dz = height_delta(x, y, style, rise, xmin, xmax, ymin, ymax, ridge_x, ridge_y)
                new_vertices.append((x, y, z + dz))
                modified_top_vertices += 1
                changed = True
            else:
                new_vertices.append((x, y, z))
        if changed:
            new_fields = list(fields[:11])
            for x, y, z in new_vertices:
                new_fields.extend([format_number(x), format_number(y), format_number(z)])
            fields = new_fields
        new_objects.append(list(fields))

    report = {
        "style": style,
        "rise": rise,
        "top_z": top_z,
        "bbox": {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax},
        "ridge_x": ridge_x if style == "gable-x" else None,
        "ridge_y": ridge_y if style == "gable-y" else None,
        "modified_top_vertices": modified_top_vertices,
    }
    return new_objects, report


def point_in_polygon(x: float, y: float, polygon: Sequence[Tuple[float, float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or TOL) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def decompose_roof_polygon(vertices: Sequence[Point3]) -> List[Tuple[float, float, float, float]]:
    xy = [(x, y) for x, y, _ in vertices]
    xs = sorted({round(x, 7) for x, _, _ in vertices})
    ys = sorted({round(y, 7) for _, y, _ in vertices})
    rects: List[Tuple[float, float, float, float]] = []
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            x1, x2 = xs[ix], xs[ix + 1]
            y1, y2 = ys[iy], ys[iy + 1]
            if x2 - x1 <= TOL or y2 - y1 <= TOL:
                continue
            cx = 0.5 * (x1 + x2)
            cy = 0.5 * (y1 + y2)
            if point_in_polygon(cx, cy, xy):
                rects.append((x1, x2, y1, y2))
    if not rects and len(vertices) == 4:
        xs4 = [x for x, _, _ in vertices]
        ys4 = [y for _, y, _ in vertices]
        rects.append((min(xs4), max(xs4), min(ys4), max(ys4)))
    return rects


def remove_collinear_2d(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(points) <= 3:
        return points
    changed = True
    result = points[:]
    while changed and len(result) > 3:
        changed = False
        cleaned: List[Tuple[float, float]] = []
        n = len(result)
        for index, point in enumerate(result):
            prev = result[(index - 1) % n]
            nxt = result[(index + 1) % n]
            same_x = abs(prev[0] - point[0]) <= TOL and abs(point[0] - nxt[0]) <= TOL
            same_y = abs(prev[1] - point[1]) <= TOL and abs(point[1] - nxt[1]) <= TOL
            if same_x or same_y:
                changed = True
                continue
            cleaned.append(point)
        result = cleaned
    return result


def rects_to_polygons(rects: Sequence[Tuple[float, float, float, float]]) -> List[List[Tuple[float, float]]]:
    if not rects:
        return []
    xs = sorted({round(value, 7) for rect in rects for value in (rect[0], rect[1])})
    ys = sorted({round(value, 7) for rect in rects for value in (rect[2], rect[3])})
    x_index = {value: index for index, value in enumerate(xs)}
    y_index = {value: index for index, value in enumerate(ys)}
    filled: Set[Tuple[int, int]] = set()
    for rect in rects:
        x1, x2, y1, y2 = (round(rect[0], 7), round(rect[1], 7), round(rect[2], 7), round(rect[3], 7))
        for ix in range(x_index[x1], x_index[x2]):
            for iy in range(y_index[y1], y_index[y2]):
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
            next_point = None
            for candidate in outgoing.get(current, []):
                edge = (current, candidate)
                if edge in unused:
                    next_point = candidate
                    unused.remove(edge)
                    break
            if next_point is None:
                raise ValueError("Could not trace merged roof polygon boundary")
            current = next_point
        coords = [(xs[ix], ys[iy]) for ix, iy in loop]
        coords = remove_collinear_2d(coords)
        if len(coords) >= 3:
            loops.append(coords)
    return loops


def surface_fields(base: Sequence[str], surface_id: str, vertices: Sequence[Point3]) -> List[str]:
    fields = list(base[:11])
    fields[1] = surface_id
    pts = avoid_triangle_surface(vertices)
    fields[10] = str(len(pts))
    for x, y, z in pts:
        fields.extend([format_number(x), format_number(y), format_number(z)])
    return fields


def avoid_triangle_surface(vertices: Sequence[Point3]) -> List[Point3]:
    pts = list(vertices)
    if len(pts) != 3:
        return pts
    longest_index = 0
    longest_length = -1.0
    for index, point in enumerate(pts):
        nxt = pts[(index + 1) % 3]
        length = norm(vector_sub(nxt, point))
        if length > longest_length:
            longest_index = index
            longest_length = length
    a = pts[longest_index]
    b = pts[(longest_index + 1) % 3]
    c = pts[(longest_index + 2) % 3]
    midpoint = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), 0.5 * (a[2] + b[2]))
    alpha = 1.0e-3
    inset = (
        midpoint[0] * (1.0 - alpha) + c[0] * alpha,
        midpoint[1] * (1.0 - alpha) + c[1] * alpha,
        midpoint[2] * (1.0 - alpha) + c[2] * alpha,
    )
    return pts[: longest_index + 1] + [inset] + pts[longest_index + 1 :]


def local_gable_ridge_axis(rects: Sequence[Tuple[float, float, float, float]]) -> str:
    xmin = min(rect[0] for rect in rects)
    xmax = max(rect[1] for rect in rects)
    ymin = min(rect[2] for rect in rects)
    ymax = max(rect[3] for rect in rects)
    return "x" if (xmax - xmin) >= (ymax - ymin) else "y"


def local_gable_planes(
    rect: Tuple[float, float, float, float],
    z: float,
    rise: float,
    ridge_axis: str | None = None,
) -> List[List[Point3]]:
    x1, x2, y1, y2 = rect
    width = x2 - x1
    depth = y2 - y1
    if ridge_axis is None:
        ridge_axis = "x" if width >= depth else "y"
    if ridge_axis == "x":
        ridge_y = 0.5 * (y1 + y2)
        return [
            [(x1, y1, z), (x2, y1, z), (x2, ridge_y, z + rise), (x1, ridge_y, z + rise)],
            [(x1, ridge_y, z + rise), (x2, ridge_y, z + rise), (x2, y2, z), (x1, y2, z)],
        ]
    if ridge_axis != "y":
        raise ValueError(f"Unsupported local-gable ridge axis: {ridge_axis}")
    ridge_x = 0.5 * (x1 + x2)
    return [
        [(x1, y1, z), (ridge_x, y1, z + rise), (ridge_x, y2, z + rise), (x1, y2, z)],
        [(ridge_x, y1, z + rise), (x2, y1, z), (x2, y2, z), (ridge_x, y2, z + rise)],
    ]


def gable_end_triangles(
    rect: Tuple[float, float, float, float],
    z: float,
    rise: float,
    ridge_axis: str | None = None,
) -> List[Tuple[str, List[Point3]]]:
    x1, x2, y1, y2 = rect
    width = x2 - x1
    depth = y2 - y1
    if ridge_axis is None:
        ridge_axis = "x" if width >= depth else "y"
    if ridge_axis == "x":
        ridge_y = 0.5 * (y1 + y2)
        return [
            ("west", [(x1, y1, z), (x1, y2, z), (x1, ridge_y, z + rise)]),
            ("east", [(x2, y2, z), (x2, y1, z), (x2, ridge_y, z + rise)]),
        ]
    if ridge_axis != "y":
        raise ValueError(f"Unsupported local-gable ridge axis: {ridge_axis}")
    ridge_x = 0.5 * (x1 + x2)
    return [
        ("south", [(x2, y1, z), (x1, y1, z), (ridge_x, y1, z + rise)]),
        ("north", [(x1, y2, z), (x2, y2, z), (ridge_x, y2, z + rise)]),
    ]


def polygon_normal(points: Sequence[Point3]) -> Point3:
    if len(points) < 3:
        return (0.0, 0.0, 0.0)
    p0 = points[0]
    for index in range(1, len(points) - 1):
        normal = cross(vector_sub(points[index], p0), vector_sub(points[index + 1], p0))
        if norm(normal) > TOL:
            return normal
    return (0.0, 0.0, 0.0)


def orient_to_normal(points: Sequence[Point3], expected_normal: Point3) -> List[Point3]:
    pts = list(points)
    normal = polygon_normal(pts)
    if norm(normal) <= TOL or norm(expected_normal) <= TOL:
        return pts
    if dot(normal, expected_normal) < 0:
        pts.reverse()
    return pts


def expected_side_normal(side: str) -> Point3:
    if side == "west":
        return (-1.0, 0.0, 0.0)
    if side == "east":
        return (1.0, 0.0, 0.0)
    if side == "south":
        return (0.0, -1.0, 0.0)
    if side == "north":
        return (0.0, 1.0, 0.0)
    raise ValueError(f"Unsupported side: {side}")


def set_vertices(fields: Sequence[str], vertices: Sequence[Point3]) -> List[str]:
    new_fields = list(fields[:11])
    new_fields[10] = str(len(vertices))
    for x, y, z in vertices:
        new_fields.extend([format_number(x), format_number(y), format_number(z)])
    return new_fields


def is_wall_fields(fields: Sequence[str]) -> bool:
    return fields[0].lower() == "buildingsurface:detailed" and fields[2].lower() == "wall"


def coordinate_span(values: Sequence[float]) -> Tuple[float, float]:
    return (min(values), max(values))


def wall_matches_roof_side(fields: Sequence[str], zone: str, rect: Tuple[float, float, float, float], side: str, z: float) -> bool:
    if not is_wall_fields(fields) or fields[4] != zone:
        return False
    vertices = vertices_from_fields(fields, 10)
    if not vertices or abs(max(vertex[2] for vertex in vertices) - z) > 1.0e-5:
        return False
    x1, x2, y1, y2 = rect
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    wx1, wx2 = coordinate_span(xs)
    wy1, wy2 = coordinate_span(ys)
    if side == "west":
        return abs(wx1 - x1) <= 1.0e-5 and abs(wx2 - x1) <= 1.0e-5 and interval_overlap(wy1, wy2, y1, y2) >= (y2 - y1) - 1.0e-5
    if side == "east":
        return abs(wx1 - x2) <= 1.0e-5 and abs(wx2 - x2) <= 1.0e-5 and interval_overlap(wy1, wy2, y1, y2) >= (y2 - y1) - 1.0e-5
    if side == "south":
        return abs(wy1 - y1) <= 1.0e-5 and abs(wy2 - y1) <= 1.0e-5 and interval_overlap(wx1, wx2, x1, x2) >= (x2 - x1) - 1.0e-5
    if side == "north":
        return abs(wy1 - y2) <= 1.0e-5 and abs(wy2 - y2) <= 1.0e-5 and interval_overlap(wx1, wx2, x1, x2) >= (x2 - x1) - 1.0e-5
    return False


def find_side_wall(
    wall_fields: Sequence[Sequence[str]],
    zone: str,
    rect: Tuple[float, float, float, float],
    side: str,
    z: float,
    boundary_condition: str | None = None,
) -> List[str] | None:
    candidates = []
    for fields in wall_fields:
        if boundary_condition is not None and fields[5].lower() != boundary_condition.lower():
            continue
        if wall_matches_roof_side(fields, zone, rect, side, z):
            candidates.append(list(fields))
    if not candidates:
        return None
    return min(candidates, key=lambda fields: abs(rect_area(wall_rect(fields)) - rect_area(rect)))


def wall_rect(fields: Sequence[str]) -> Tuple[float, float, float, float]:
    vertices = vertices_from_fields(fields, 10)
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    return (min(xs), max(xs), min(ys), max(ys))


def triangle_wall_vertices(rect: Tuple[float, float, float, float], side: str, z: float, rise: float) -> List[Point3]:
    x1, x2, y1, y2 = rect
    if side in ("west", "east"):
        x = x1 if side == "west" else x2
        ridge_y = 0.5 * (y1 + y2)
        return [(x, y1, z), (x, y2, z), (x, ridge_y, z + rise)]
    y = y1 if side == "south" else y2
    ridge_x = 0.5 * (x1 + x2)
    return [(x1, y, z), (x2, y, z), (ridge_x, y, z + rise)]


def merged_gable_wall_vertices(
    wall_fields: Sequence[str],
    rect: Tuple[float, float, float, float],
    side: str,
    z: float,
    rise: float,
) -> List[Point3]:
    vertices = vertices_from_fields(wall_fields, 10)
    bottom_z = min(vertex[2] for vertex in vertices)
    x1, x2, y1, y2 = rect
    if side == "west":
        x = x1
        ridge_y = 0.5 * (y1 + y2)
        pts = [(x, y2, bottom_z), (x, y1, bottom_z), (x, y1, z), (x, ridge_y, z + rise), (x, y2, z)]
    elif side == "east":
        x = x2
        ridge_y = 0.5 * (y1 + y2)
        pts = [(x, y2, z), (x, ridge_y, z + rise), (x, y1, z), (x, y1, bottom_z), (x, y2, bottom_z)]
    elif side == "south":
        y = y1
        ridge_x = 0.5 * (x1 + x2)
        pts = [(x1, y, bottom_z), (x2, y, bottom_z), (x2, y, z), (ridge_x, y, z + rise), (x1, y, z)]
    elif side == "north":
        y = y2
        ridge_x = 0.5 * (x1 + x2)
        pts = [(x2, y, bottom_z), (x1, y, bottom_z), (x1, y, z), (ridge_x, y, z + rise), (x2, y, z)]
    else:
        raise ValueError(f"Unsupported side: {side}")
    return orient_to_normal(pts, polygon_normal(vertices))


def adjacent_gable_wall_fields(base_wall: Sequence[str], surface_id: str, vertices: Sequence[Point3]) -> List[str]:
    expected = polygon_normal(vertices_from_fields(base_wall, 10))
    return set_vertices([*base_wall[:1], surface_id, *base_wall[2:11]], orient_to_normal(vertices, expected))


def interval_overlap(a1: float, a2: float, b1: float, b2: float) -> float:
    return min(a2, b2) - max(a1, b1)


def has_neighbor(rect: Tuple[float, float, float, float], side: str, all_rects: Sequence[Tuple[float, float, float, float]]) -> bool:
    x1, x2, y1, y2 = rect
    for other in all_rects:
        if other == rect:
            continue
        ox1, ox2, oy1, oy2 = other
        if side == "west" and abs(ox2 - x1) <= TOL and interval_overlap(oy1, oy2, y1, y2) > TOL:
            return True
        if side == "east" and abs(ox1 - x2) <= TOL and interval_overlap(oy1, oy2, y1, y2) > TOL:
            return True
        if side == "south" and abs(oy2 - y1) <= TOL and interval_overlap(ox1, ox2, x1, x2) > TOL:
            return True
        if side == "north" and abs(oy1 - y2) <= TOL and interval_overlap(ox1, ox2, x1, x2) > TOL:
            return True
    return False


def rect_area(rect: Tuple[float, float, float, float]) -> float:
    x1, x2, y1, y2 = rect
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def positive_rect_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return interval_overlap(a[0], a[1], b[0], b[1]) > TOL and interval_overlap(a[2], a[3], b[2], b[3]) > TOL


def rect_center(rect: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return (0.5 * (rect[0] + rect[1]), 0.5 * (rect[2] + rect[3]))


def find_courtyard_hole(rects: Sequence[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float] | None:
    xs = sorted({coord for rect in rects for coord in (rect[0], rect[1])})
    ys = sorted({coord for rect in rects for coord in (rect[2], rect[3])})
    if len(xs) < 3 or len(ys) < 3:
        return None

    occupied = set()
    empty = set()
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            cell = (xs[ix], xs[ix + 1], ys[iy], ys[iy + 1])
            if rect_area(cell) <= TOL:
                continue
            cx, cy = rect_center(cell)
            if any((rect[0] - TOL) <= cx <= (rect[1] + TOL) and (rect[2] - TOL) <= cy <= (rect[3] + TOL) for rect in rects):
                occupied.add((ix, iy))
            else:
                empty.add((ix, iy))

    visited = set()
    candidates: List[Tuple[float, Tuple[float, float, float, float]]] = []
    max_ix = len(xs) - 2
    max_iy = len(ys) - 2
    for start in sorted(empty):
        if start in visited:
            continue
        stack = [start]
        component = []
        touches_boundary = False
        visited.add(start)
        while stack:
            ix, iy = stack.pop()
            component.append((ix, iy))
            if ix == 0 or ix == max_ix or iy == 0 or iy == max_iy:
                touches_boundary = True
            for nxt in ((ix - 1, iy), (ix + 1, iy), (ix, iy - 1), (ix, iy + 1)):
                if nxt in empty and nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        if touches_boundary:
            continue
        hx1 = min(xs[ix] for ix, _ in component)
        hx2 = max(xs[ix + 1] for ix, _ in component)
        hy1 = min(ys[iy] for _, iy in component)
        hy2 = max(ys[iy + 1] for _, iy in component)
        area = sum(rect_area((xs[ix], xs[ix + 1], ys[iy], ys[iy + 1])) for ix, iy in component)
        candidates.append((area, (hx1, hx2, hy1, hy2)))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def merge_rect_group(rects: Sequence[Tuple[float, float, float, float]]) -> List[Tuple[float, float, float, float]]:
    if not rects:
        return []
    x1 = min(rect[0] for rect in rects)
    x2 = max(rect[1] for rect in rects)
    y1 = min(rect[2] for rect in rects)
    y2 = max(rect[3] for rect in rects)
    bbox_rect = (x1, x2, y1, y2)
    if abs(rect_area(bbox_rect) - sum(rect_area(rect) for rect in rects)) <= 1.0e-5:
        return [bbox_rect]
    return list(rects)


def split_rect_at(rect: Tuple[float, float, float, float], axis: str, value: float) -> List[Tuple[float, float, float, float]]:
    x1, x2, y1, y2 = rect
    if axis == "x" and (x1 + TOL) < value < (x2 - TOL):
        return [(x1, value, y1, y2), (value, x2, y1, y2)]
    if axis == "y" and (y1 + TOL) < value < (y2 - TOL):
        return [(x1, x2, y1, value), (x1, x2, value, y2)]
    return [rect]


def strip_height(
    x: float,
    y: float,
    side: str,
    z: float,
    rise: float,
    strip_bounds: Tuple[float, float],
) -> float:
    low, high = strip_bounds
    center = 0.5 * (low + high)
    half = max(0.5 * (high - low), TOL)
    coordinate = y if side in ("south", "north") else x
    return z + rise * max(0.0, 1.0 - abs(coordinate - center) / half)


def side_roof_planes(
    rect: Tuple[float, float, float, float],
    side: str,
    z: float,
    rise: float,
    strip_bounds: Tuple[float, float],
) -> List[List[Point3]]:
    ridge = 0.5 * (strip_bounds[0] + strip_bounds[1])
    axis = "y" if side in ("south", "north") else "x"
    planes = []
    for subrect in split_rect_at(rect, axis, ridge):
        x1, x2, y1, y2 = subrect
        planes.append(
            [
                (x1, y1, strip_height(x1, y1, side, z, rise, strip_bounds)),
                (x2, y1, strip_height(x2, y1, side, z, rise, strip_bounds)),
                (x2, y2, strip_height(x2, y2, side, z, rise, strip_bounds)),
                (x1, y2, strip_height(x1, y2, side, z, rise, strip_bounds)),
            ]
        )
    return planes


def side_gable_triangles(
    rect: Tuple[float, float, float, float],
    side: str,
    z: float,
    rise: float,
    strip_bounds: Tuple[float, float],
    extents: dict,
) -> List[Tuple[str, List[Point3]]]:
    x1, x2, y1, y2 = rect
    low, high = strip_bounds
    center = 0.5 * (low + high)
    triangles: List[Tuple[str, List[Point3]]] = []

    if side in ("south", "north"):
        for label, x in (("west", x1), ("east", x2)):
            if not (abs(x - extents["outer_xmin"]) <= TOL or abs(x - extents["outer_xmax"]) <= TOL):
                continue
            triangles.append(
                (
                    label,
                    [
                        (x, low, z),
                        (x, high, z),
                        (x, center, z + rise),
                    ],
                )
            )
    else:
        for label, y in (("south", y1), ("north", y2)):
            if not (abs(y - extents["hole_ymin"]) <= TOL or abs(y - extents["hole_ymax"]) <= TOL):
                continue
            triangles.append(
                (
                    label,
                    [
                        (low, y, z),
                        (high, y, z),
                        (center, y, z + rise),
                    ],
                )
            )
    return triangles


def signed_area_xy(points: Sequence[Point3]) -> float:
    area = 0.0
    for index, (x1, y1, _) in enumerate(points):
        x2, y2, _ = points[(index + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return 0.5 * area


def vector_sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Point3) -> float:
    return (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) ** 0.5


def plane_key_from_points(points: Sequence[Point3]) -> Tuple[float, float, float, float]:
    if len(points) < 3:
        raise ValueError("At least three points are required for a plane")
    p0 = points[0]
    normal = None
    for i in range(1, len(points) - 1):
        candidate = cross(vector_sub(points[i], p0), vector_sub(points[i + 1], p0))
        length = norm(candidate)
        if length > TOL:
            normal = (candidate[0] / length, candidate[1] / length, candidate[2] / length)
            break
    if normal is None:
        raise ValueError("Degenerate polygon cannot define a plane")
    if normal[2] < -TOL or (abs(normal[2]) <= TOL and tuple(normal) < (0.0, 0.0, 0.0)):
        normal = (-normal[0], -normal[1], -normal[2])
    d = -dot(normal, p0)
    return tuple(round(value, 7) for value in (*normal, d))  # type: ignore[return-value]


def point_key(point: Point3) -> Tuple[float, float, float]:
    return (round(point[0], 7), round(point[1], 7), round(point[2], 7))


def remove_collinear_3d(points: List[Point3]) -> List[Point3]:
    if len(points) <= 3:
        return points
    changed = True
    result = points[:]
    while changed and len(result) > 3:
        changed = False
        cleaned: List[Point3] = []
        n = len(result)
        for index, point in enumerate(result):
            prev = result[(index - 1) % n]
            nxt = result[(index + 1) % n]
            v1 = vector_sub(point, prev)
            v2 = vector_sub(nxt, point)
            if norm(cross(v1, v2)) <= 1.0e-6:
                changed = True
                continue
            cleaned.append(point)
        result = cleaned
    return result


def orient_polygon(points: List[Point3]) -> List[Point3]:
    if len(points) >= 3 and signed_area_xy(points) < 0:
        return list(reversed(points))
    return points


def merge_coplanar_polygons(polygons: Sequence[Sequence[Point3]]) -> List[List[Point3]]:
    edge_counts: Dict[Tuple[Tuple[float, float, float], Tuple[float, float, float]], int] = {}
    key_to_point: Dict[Tuple[float, float, float], Point3] = {}
    for polygon in polygons:
        pts = orient_polygon(list(polygon))
        for point in pts:
            key_to_point[point_key(point)] = point
        for index, a in enumerate(pts):
            b = pts[(index + 1) % len(pts)]
            ka = point_key(a)
            kb = point_key(b)
            edge = tuple(sorted((ka, kb)))  # type: ignore[arg-type]
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

    boundary_edges = {edge for edge, count in edge_counts.items() if count == 1}
    adjacency: Dict[Tuple[float, float, float], Set[Tuple[float, float, float]]] = {}
    for a, b in boundary_edges:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    loops: List[List[Point3]] = []
    remaining = set(boundary_edges)
    while remaining:
        start, nxt = min(remaining)
        current = start
        loop_keys = [start]
        while True:
            edge = tuple(sorted((current, nxt)))  # type: ignore[arg-type]
            if edge not in remaining:
                break
            remaining.remove(edge)
            previous = current
            current = nxt
            if current == start:
                break
            loop_keys.append(current)
            candidates = [
                candidate
                for candidate in adjacency.get(current, set())
                if tuple(sorted((current, candidate))) in remaining  # type: ignore[arg-type]
            ]
            if not candidates:
                break
            if len(candidates) == 1:
                nxt = candidates[0]
            else:
                px, py, _ = key_to_point[previous]
                cx, cy, _ = key_to_point[current]
                incoming_angle = math.atan2(cy - py, cx - px)

                def turn_angle(candidate: Tuple[float, float, float]) -> float:
                    qx, qy, _ = key_to_point[candidate]
                    outgoing_angle = math.atan2(qy - cy, qx - cx)
                    return (outgoing_angle - incoming_angle) % (2.0 * math.pi)

                nxt = max(candidates, key=turn_angle)
        if len(loop_keys) >= 3 and current == start:
            deduped = []
            for key in loop_keys:
                if not deduped or deduped[-1] != key:
                    deduped.append(key)
            if len(deduped) > 1 and deduped[0] == deduped[-1]:
                deduped.pop()
            if len(set(deduped)) != len(deduped):
                continue
            points = [key_to_point[key] for key in deduped]
            points = orient_polygon(remove_collinear_3d(points))
            if len(points) >= 3:
                loops.append(points)
    return loops


def roof_delta_for_side(x: float, y: float, side: str, rise: float, extents: dict) -> float:
    low, high = side_bounds(side, extents)
    coordinate = y if side in ("south", "north") else x
    center = 0.5 * (low + high)
    half = max(0.5 * (high - low), TOL)
    return rise * max(0.0, 1.0 - abs(coordinate - center) / half)


def courtyard_roof_height(x: float, y: float, z: float, rise: float, hole: Tuple[float, float, float, float], extents: dict) -> float:
    hx1, hx2, hy1, hy2 = hole
    deltas: List[float] = []
    if y <= hy1 + TOL:
        deltas.append(roof_delta_for_side(x, y, "south", rise, extents))
    if y >= hy2 - TOL:
        deltas.append(roof_delta_for_side(x, y, "north", rise, extents))
    if x <= hx1 + TOL:
        deltas.append(roof_delta_for_side(x, y, "west", rise, extents))
    if x >= hx2 - TOL:
        deltas.append(roof_delta_for_side(x, y, "east", rise, extents))
    return z + max(deltas or [0.0])


def active_roof_planes(
    x: float,
    y: float,
    hole: Tuple[float, float, float, float],
    extents: dict,
    rise: float,
) -> List[str]:
    hx1, hx2, hy1, hy2 = hole
    candidates: List[Tuple[float, str]] = []
    if y <= hy1 + TOL:
        candidates.append((roof_delta_for_side(x, y, "south", rise, extents), "south"))
    if y >= hy2 - TOL:
        candidates.append((roof_delta_for_side(x, y, "north", rise, extents), "north"))
    if x <= hx1 + TOL:
        candidates.append((roof_delta_for_side(x, y, "west", rise, extents), "west"))
    if x >= hx2 - TOL:
        candidates.append((roof_delta_for_side(x, y, "east", rise, extents), "east"))
    if not candidates:
        return ["flat"]
    max_delta = max(delta for delta, _ in candidates)
    return sorted(side for delta, side in candidates if abs(delta - max_delta) <= 1.0e-6)


def roof_plane_key(
    x: float,
    y: float,
    hole: Tuple[float, float, float, float],
    extents: dict,
    rise: float,
) -> str:
    active = active_roof_planes(x, y, hole, extents, rise)
    if len(active) != 1:
        return "valley_" + "_".join(active)
    side = active[0]
    if side in ("south", "north"):
        low, high = side_bounds(side, extents)
        center = 0.5 * (low + high)
        return f"{side}_{'low' if y < center else 'high'}"
    if side in ("west", "east"):
        low, high = side_bounds(side, extents)
        center = 0.5 * (low + high)
        return f"{side}_{'low' if x < center else 'high'}"
    return side


def point_covered_by_rects(x: float, y: float, rects: Sequence[Tuple[float, float, float, float]]) -> bool:
    return any((rect[0] - TOL) <= x <= (rect[1] + TOL) and (rect[2] - TOL) <= y <= (rect[3] + TOL) for rect in rects)


def roof_boundary_edge(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    side: str,
    rects: Sequence[Tuple[float, float, float, float]],
) -> bool:
    mx = 0.5 * (p1[0] + p2[0])
    my = 0.5 * (p1[1] + p2[1])
    eps = 1.0e-5
    if side == "west":
        mx -= eps
    elif side == "east":
        mx += eps
    elif side == "south":
        my -= eps
    elif side == "north":
        my += eps
    return not point_covered_by_rects(mx, my, rects)


def triangle_fields(base: Sequence[str], surface_id: str, vertices: Sequence[Point3]) -> List[str]:
    pts = list(vertices)
    if signed_area_xy(pts) < 0:
        pts.reverse()
    return surface_fields(base, surface_id, avoid_triangle_surface(pts))


def vertical_edge_wall(
    base: Sequence[str],
    surface_id: str,
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    z: float,
    h1: float,
    h2: float,
) -> List[str] | None:
    if abs(h1 - z) <= TOL and abs(h2 - z) <= TOL:
        return None
    x1, y1 = p1
    x2, y2 = p2
    if abs(h1 - z) <= TOL:
        pts: List[Point3] = [(x1, y1, z), (x2, y2, z), (x2, y2, h2)]
    elif abs(h2 - z) <= TOL:
        pts = [(x1, y1, z), (x2, y2, z), (x1, y1, h1)]
    else:
        pts = [(x1, y1, z), (x2, y2, z), (x2, y2, h2), (x1, y1, h1)]
    return gable_wall_fields(base, surface_id, pts)


def lift_local_gable_courtyard_mesh(
    objects: Sequence[List[str]],
    rise: float,
    hole: Tuple[float, float, float, float],
    extents: dict,
    all_rects: Sequence[Tuple[float, float, float, float]],
) -> Tuple[List[List[str]], dict]:
    new_objects: List[List[str]] = []
    replaced_roofs = 0
    decomposed_rectangles = 0
    generated_roofs = 0
    merged_cells = 0

    for fields in objects:
        if not is_roof_fields(fields):
            new_objects.append(list(fields))
            continue
        replaced_roofs += 1
        vertices = vertices_from_fields(fields, 10)
        z = sum(vertex[2] for vertex in vertices) / len(vertices)
        rects = decompose_roof_polygon(vertices)
        decomposed_rectangles += len(rects)

        for rect_index, rect in enumerate(rects, 1):
            x1, x2, y1, y2 = rect
            cx = 0.5 * (x1 + x2)
            cy = 0.5 * (y1 + y2)
            side = classify_roof_rect(rect, hole)
            if side is None:
                side = "south" if cy < 0.5 * (hole[2] + hole[3]) else "north"
            bounds = side_bounds(side, extents)
            planes = side_roof_planes(rect, side, z, rise, bounds)
            for plane_index, plane in enumerate(planes, 1):
                surface_id = f"{fields[1]}_lg_merged_{rect_index:03d}_{plane_index}"
                new_objects.append(surface_fields(fields, surface_id, plane))
                generated_roofs += 1
            merged_cells += 1

    report = {
        "style": "local-gable",
        "rise": rise,
        "replaced_roof_surfaces": replaced_roofs,
        "decomposed_rectangles": decomposed_rectangles,
        "generated_strip_parts": merged_cells,
        "generated_roof_surfaces": generated_roofs,
        "generated_gable_end_surfaces": 0,
        "modified_top_vertices": 0,
        "courtyard_hole": {
            "xmin": hole[0],
            "xmax": hole[1],
            "ymin": hole[2],
            "ymax": hole[3],
        },
        "note": "Courtyard local-gable strip mode: each original roof rectangle is fully covered by one or two quadrilateral sloped roof surfaces. South/north/east/west strips use local ridge directions, avoiding triangular meshes, degenerate quads, and uncovered corner holes.",
    }
    return new_objects, report


def classify_roof_rect(
    rect: Tuple[float, float, float, float],
    hole: Tuple[float, float, float, float],
) -> str | None:
    hx1, hx2, hy1, hy2 = hole
    x1, x2, y1, y2 = rect
    if y2 <= hy1 + TOL:
        return "south"
    if y1 >= hy2 - TOL:
        return "north"
    if x2 <= hx1 + TOL and interval_overlap(y1, y2, hy1, hy2) > TOL:
        return "west"
    if x1 >= hx2 - TOL and interval_overlap(y1, y2, hy1, hy2) > TOL:
        return "east"
    return None


def strip_extents(
    rects: Sequence[Tuple[float, float, float, float]],
    hole: Tuple[float, float, float, float],
) -> dict:
    hx1, hx2, hy1, hy2 = hole
    outer_xmin = min(rect[0] for rect in rects)
    outer_xmax = max(rect[1] for rect in rects)
    outer_ymin = min(rect[2] for rect in rects)
    outer_ymax = max(rect[3] for rect in rects)
    west_rects = [rect for rect in rects if rect[1] <= hx1 + TOL and interval_overlap(rect[2], rect[3], hy1, hy2) > TOL]
    east_rects = [rect for rect in rects if rect[0] >= hx2 - TOL and interval_overlap(rect[2], rect[3], hy1, hy2) > TOL]
    return {
        "outer_xmin": outer_xmin,
        "outer_xmax": outer_xmax,
        "outer_ymin": outer_ymin,
        "outer_ymax": outer_ymax,
        "hole_xmin": hx1,
        "hole_xmax": hx2,
        "hole_ymin": hy1,
        "hole_ymax": hy2,
        "west_xmin": min((rect[0] for rect in west_rects), default=outer_xmin),
        "east_xmax": max((rect[1] for rect in east_rects), default=outer_xmax),
    }


def side_bounds(side: str, extents: dict) -> Tuple[float, float]:
    if side == "south":
        return (extents["outer_ymin"], extents["hole_ymin"])
    if side == "north":
        return (extents["hole_ymax"], extents["outer_ymax"])
    if side == "west":
        return (extents["west_xmin"], extents["hole_xmin"])
    if side == "east":
        return (extents["hole_xmax"], extents["east_xmax"])
    raise ValueError(f"Unknown side: {side}")


def gable_wall_fields(
    base: Sequence[str],
    surface_id: str,
    vertices: Sequence[Point3],
    expected_normal: Point3 | None = None,
) -> List[str]:
    fields = list(base[:11])
    fields[1] = surface_id
    fields[2] = "Wall"
    fields[3] = "EXT_WALL"
    fields[5] = "Outdoors"
    fields[6] = ""
    fields[7] = "SunExposed"
    fields[8] = "WindExposed"
    pts = orient_to_normal(vertices, expected_normal) if expected_normal is not None else list(vertices)
    return set_vertices(fields, pts)


def is_roof_fields(fields: Sequence[str]) -> bool:
    return fields[0].lower() == "buildingsurface:detailed" and (
        fields[2].lower() == "roof" or fields[3].upper() == "EXT_ROOF"
    )


def lift_local_gable(objects: Sequence[List[str]], rise: float) -> Tuple[List[List[str]], dict]:
    roof_entries: List[Tuple[List[str], Tuple[float, float, float, float], float, str | None]] = []
    for fields in objects:
        if not is_roof_fields(fields):
            continue
        vertices = vertices_from_fields(fields, 10)
        z = sum(vertex[2] for vertex in vertices) / len(vertices)
        for rect in decompose_roof_polygon(vertices):
            roof_entries.append((list(fields), rect, z, None))

    all_rects = [entry[1] for entry in roof_entries]
    hole = find_courtyard_hole(all_rects)
    if hole is None:
        return lift_local_gable_per_rect(objects, rise)
    extents = strip_extents(all_rects, hole)
    return lift_local_gable_courtyard_mesh(objects, rise, hole, extents, all_rects)


def lift_local_gable_per_rect(objects: Sequence[List[str]], rise: float) -> Tuple[List[List[str]], dict]:
    roof_entries: List[Tuple[List[str], Tuple[float, float, float, float], float]] = []
    for fields in objects:
        if not is_roof_fields(fields):
            continue
        vertices = vertices_from_fields(fields, 10)
        z = sum(vertex[2] for vertex in vertices) / len(vertices)
        for rect in decompose_roof_polygon(vertices):
            roof_entries.append((list(fields), rect, z))

    all_rects = [entry[1] for entry in roof_entries]
    ridge_axis = local_gable_ridge_axis(all_rects)
    wall_fields = [list(fields) for fields in objects if is_wall_fields(fields)]
    exterior_wall_replacements: Dict[str, List[str]] = {}
    merged_exterior_gables = 0
    for roof_fields, rect, z in roof_entries:
        zone = roof_fields[4]
        for side, _ in gable_end_triangles(rect, z, rise, ridge_axis):
            exterior_wall = find_side_wall(wall_fields, zone, rect, side, z, "outdoors")
            if exterior_wall is None or exterior_wall[1] in exterior_wall_replacements:
                continue
            merged_vertices = merged_gable_wall_vertices(exterior_wall, rect, side, z, rise)
            exterior_wall_replacements[exterior_wall[1]] = set_vertices(exterior_wall, merged_vertices)
            merged_exterior_gables += 1

    new_objects: List[List[str]] = []
    replaced_roofs = 0
    generated_roofs = 0
    decomposed_rectangles = 0
    generated_adjacent_gables = 0
    generated_exterior_gables = 0
    for fields in objects:
        if not is_roof_fields(fields):
            if is_wall_fields(fields) and fields[1] in exterior_wall_replacements:
                new_objects.append(exterior_wall_replacements[fields[1]])
            else:
                new_objects.append(list(fields))
            continue
        replaced_roofs += 1
        vertices = vertices_from_fields(fields, 10)
        z = sum(vertex[2] for vertex in vertices) / len(vertices)
        rects = decompose_roof_polygon(vertices)
        decomposed_rectangles += len(rects)
        for rect_index, rect in enumerate(rects, 1):
            for plane_index, plane in enumerate(local_gable_planes(rect, z, rise, ridge_axis), 1):
                surface_id = f"{fields[1]}_lg{rect_index:02d}{plane_index}"
                new_objects.append(surface_fields(fields, surface_id, plane))
                generated_roofs += 1
            for side, triangle in gable_end_triangles(rect, z, rise, ridge_axis):
                adjacent_wall = find_side_wall(wall_fields, fields[4], rect, side, z, "zone")
                if adjacent_wall is not None:
                    surface_id = f"{adjacent_wall[1]}_lg{rect_index:02d}_{side}_gable"
                    new_objects.append(adjacent_gable_wall_fields(adjacent_wall, surface_id, triangle_wall_vertices(rect, side, z, rise)))
                    generated_adjacent_gables += 1
                    continue
                if find_side_wall(wall_fields, fields[4], rect, side, z, "outdoors") is not None:
                    continue
                surface_id = f"{fields[1]}_lg{rect_index:02d}_{side}_gable"
                new_objects.append(gable_wall_fields(fields, surface_id, triangle, expected_side_normal(side)))
                generated_exterior_gables += 1
    report = {
        "style": "local-gable",
        "rise": rise,
        "replaced_roof_surfaces": replaced_roofs,
        "decomposed_rectangles": decomposed_rectangles,
        "generated_strip_parts": decomposed_rectangles,
        "generated_roof_surfaces": generated_roofs,
        "generated_gable_end_surfaces": generated_adjacent_gables + generated_exterior_gables,
        "generated_adjacent_gable_surfaces": generated_adjacent_gables,
        "generated_exterior_gable_surfaces": generated_exterior_gables,
        "merged_exterior_gable_walls": merged_exterior_gables,
        "ridge_axis": ridge_axis,
        "modified_top_vertices": 0,
        "note": "Fallback mode: each local roof rectangle is split into two sloped planes. Exterior gable end triangles are merged into matching exterior walls, while adjacent-zone gable end triangles are retained as ADJ_WALL separators with vertex order inherited from the original wall normal.",
    }
    return new_objects, report


def render_objects(objects: Sequence[Sequence[str]]) -> str:
    chunks: List[str] = []
    for fields in objects:
        kind = fields[0]
        if kind.lower() == "zone":
            chunks.append(render_zone(fields))
        elif kind.lower() == "buildingsurface:detailed":
            chunks.append(render_surface(fields))
        elif kind.lower() == "fenestrationsurface:detailed":
            chunks.append(render_window(fields))
        else:
            chunks.append(",\n".join(fields) + ";")
    return "\n\n".join(chunks).rstrip() + "\n"


def render_zone(fields: Sequence[str]) -> str:
    return f"""  Zone,
    {fields[1]},
    {fields[2]},
    {fields[3]},
    {fields[4]},
    {fields[5]},
    {fields[6]},
    {fields[7]};
"""


def render_surface(fields: Sequence[str]) -> str:
    count = int(float(fields[10]))
    values = fields[11 : 11 + count * 3]
    vertex_lines = []
    for index in range(count):
        terminator = ";" if index == count - 1 else ","
        x, y, z = values[index * 3 : index * 3 + 3]
        vertex_lines.append(f"    {x},\n    {y},\n    {z}{terminator}")
    return f"""  BuildingSurface:Detailed,
    {fields[1]},
    {fields[2]},
    {fields[3]},
    {fields[4]},
    {fields[5]},
    {fields[6]},
    {fields[7]},
    {fields[8]},
    {fields[9]},
    {count},
{chr(10).join(vertex_lines)}
"""


def render_window(fields: Sequence[str]) -> str:
    count = int(float(fields[10]))
    values = fields[11 : 11 + count * 3]
    vertex_lines = []
    for index in range(count):
        terminator = ";" if index == count - 1 else ","
        x, y, z = values[index * 3 : index * 3 + 3]
        vertex_lines.append(f"    {x},\n    {y},\n    {z}{terminator}")
    return f"""  FenestrationSurface:Detailed,
    {fields[1]},
    {fields[2]},
    {fields[3]},
    {fields[4]},
    {fields[5]},
    {fields[6]},
    {fields[7]},
    {fields[8]},
    {fields[9]},
    {count},
{chr(10).join(vertex_lines)}
"""


def generate(args: argparse.Namespace) -> dict:
    source = Path(args.source)
    output = Path(args.output)
    text = read_text(source)
    prefix, objects, surfaces = parse_geometry(text)
    new_objects, report = lift_roof(objects, surfaces, args.style, args.rise)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prefix + "\n\n" + render_objects(new_objects), encoding="utf-8")
    report.update(
        {
            "tool": "Roof_Lifting/roof_lift_idf.py",
            "source": str(source),
            "output": str(output),
        }
    )
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lift flat IDF roofs into shed or gable roof styles by modifying top-surface vertices.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", required=True, help="Input IDF generated by a geometry postprocessor")
    parser.add_argument("--output", required=True, help="Output IDF with lifted roof")
    parser.add_argument("--style", choices=STYLES, required=True)
    parser.add_argument("--rise", type=float, default=2.0, help="Maximum roof lift height in meters")
    parser.add_argument("--report", help="Optional JSON report path")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        report = generate(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
