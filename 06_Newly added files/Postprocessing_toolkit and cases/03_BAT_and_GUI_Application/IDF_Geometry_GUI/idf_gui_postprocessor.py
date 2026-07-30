#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import importlib.util
import tkinter as tk
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from types import ModuleType
from typing import Dict, List, Optional, Sequence, Tuple

from manual_restore_wizard import (
    RESTORE13_STEPWISE_COMMANDS,
    canonical_command,
    is_restore13_stepwise_recipe,
    restore13_stepwise_status,
)


Point2 = Tuple[float, float]
Point3 = Tuple[float, float, float]

HERE = Path(__file__).resolve().parent
SUMMARY_DIR = HERE.parent
INPUT_DIR = HERE / "input"
OUTPUT_DIR = HERE / "output"
RECORDS_DIR = HERE / "records"
TOOL_BAT = SUMMARY_DIR / "Restoration_Engine" / "tool" / "idf_toolkit.bat"
REFERENCE_IDF = SUMMARY_DIR / "Restoration_Engine" / "input" / "reference_13zone.idf"
TOOLKIT_PY = TOOL_BAT.with_name("idf_toolkit.py")
_IDF_TOOLKIT: Optional[ModuleType] = None


@dataclass
class ZoneShape:
    name: str
    polygon: List[Point2]
    source: str = "input"
    command_name: str = ""

    def __post_init__(self) -> None:
        if not self.command_name:
            self.command_name = self.name


@dataclass
class GuiOperation:
    raw: str
    kind: str
    selected_zones: List[str]
    note: str


@dataclass
class CheckOperation:
    raw: str
    kind: str = "gui"


RESTORE_MERGE_ORDER = {
    frozenset(["zone01", "zone07_west"]): ["zone01", "zone07_west"],
    frozenset(["zone07_east", "zone16"]): ["zone07_east", "zone16"],
    frozenset(["zone02", "zone03"]): ["zone02", "zone03"],
    frozenset(["zone10", "zone11_east"]): ["zone10", "zone11_east"],
    frozenset(["zone13", "zone14", "zone12_west"]): ["zone13", "zone14", "zone12_west"],
}

RESTORE_TRIM_ORDER = {
    frozenset(["zone06", "zone15_west"]): ["zone06", "zone15_west"],
    frozenset(["zone15_east", "zone18"]): ["zone15_east", "zone18"],
    frozenset(["zone11_west", "zone12_east"]): ["zone11_west", "zone12_east"],
}

LINE_PARAM_TEMPLATE = "(,)-(,)"
POINTS_PARAM_TEMPLATE = "(,),(,)"

RESTORE_TRIM_DEFAULTS = {
    frozenset(["zone06", "zone15_west"]): ("zone05", "line", LINE_PARAM_TEMPLATE),
    frozenset(["zone15_east", "zone18"]): ("zone08", "line", LINE_PARAM_TEMPLATE),
    frozenset(["zone11_west", "zone12_east"]): ("zone12", "points", POINTS_PARAM_TEMPLATE),
}

RESTORE_MERGE_DEFAULT_OUTPUTS = {
    frozenset(["zone01", "zone07_west"]): "zone01",
    frozenset(["zone07_east", "zone16"]): "zone06",
    frozenset(["zone02", "zone03"]): "zone02",
    frozenset(["zone10", "zone11_east"]): "zone11",
    frozenset(["zone13", "zone14", "zone12_west"]): "zone13",
}

RESTORE_MAP_DEFAULT_OUTPUTS = {
    "zone04": "zone03",
    "zone05": "zone04",
    "zone17": "zone07",
    "zone08": "zone09",
    "zone09": "zone10",
}


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def strip_comments(text: str) -> str:
    return "\n".join(line.split("!")[0] for line in text.splitlines())


def idf_objects(text: str) -> List[List[str]]:
    objects: List[List[str]] = []
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


def polygon_area(poly: Sequence[Point2]) -> float:
    return abs(signed_polygon_area(poly))


def signed_polygon_area(poly: Sequence[Point2]) -> float:
    area = 0.0
    for index, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(index + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def polygon_centroid(poly: Sequence[Point2]) -> Point2:
    if not poly:
        return 0.0, 0.0
    return sum(x for x, _ in poly) / len(poly), sum(y for _, y in poly) / len(poly)


def point_in_polygon(point: Point2, poly: Sequence[Point2]) -> bool:
    x, y = point
    inside = False
    if not poly:
        return False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1.0e-12) + xi:
            inside = not inside
        j = i
    return inside


def simplify_ring(points: Sequence[Point2]) -> List[Point2]:
    if len(points) <= 3:
        return list(points)
    ring = list(points)
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    changed = True
    while changed and len(ring) > 3:
        changed = False
        simplified: List[Point2] = []
        count = len(ring)
        for index, point in enumerate(ring):
            prev = ring[(index - 1) % count]
            nxt = ring[(index + 1) % count]
            same_x = abs(prev[0] - point[0]) < 1.0e-9 and abs(point[0] - nxt[0]) < 1.0e-9
            same_y = abs(prev[1] - point[1]) < 1.0e-9 and abs(point[1] - nxt[1]) < 1.0e-9
            if same_x or same_y:
                changed = True
                continue
            simplified.append(point)
        ring = simplified
    return ring


def polygon_union_outline(polygons: Sequence[Sequence[Point2]]) -> Optional[List[Point2]]:
    """Return the outer boundary of a union of rectilinear polygons for GUI preview."""
    polys = [list(poly) for poly in polygons if len(poly) >= 3]
    if not polys:
        return None
    xs = sorted({round(x, 10) for poly in polys for x, _ in poly})
    ys = sorted({round(y, 10) for poly in polys for _, y in poly})
    if len(xs) < 2 or len(ys) < 2:
        return None

    occupied: set[Tuple[int, int]] = set()
    for xi in range(len(xs) - 1):
        for yi in range(len(ys) - 1):
            cx = (xs[xi] + xs[xi + 1]) * 0.5
            cy = (ys[yi] + ys[yi + 1]) * 0.5
            if any(point_in_polygon((cx, cy), poly) for poly in polys):
                occupied.add((xi, yi))
    if not occupied:
        return None

    edges: set[Tuple[Point2, Point2]] = set()

    def add_or_cancel(start: Point2, end: Point2) -> None:
        reverse = (end, start)
        if reverse in edges:
            edges.remove(reverse)
        else:
            edges.add((start, end))

    for xi, yi in occupied:
        x0, x1 = xs[xi], xs[xi + 1]
        y0, y1 = ys[yi], ys[yi + 1]
        add_or_cancel((x0, y0), (x1, y0))
        add_or_cancel((x1, y0), (x1, y1))
        add_or_cancel((x1, y1), (x0, y1))
        add_or_cancel((x0, y1), (x0, y0))

    loops: List[List[Point2]] = []
    remaining = set(edges)
    while remaining:
        start, end = remaining.pop()
        loop = [start, end]
        current = end
        while current != start:
            next_edge = None
            for edge in list(remaining):
                if edge[0] == current:
                    next_edge = edge
                    break
            if next_edge is None:
                break
            remaining.remove(next_edge)
            current = next_edge[1]
            loop.append(current)
        if len(loop) > 3 and loop[-1] == loop[0]:
            loops.append(simplify_ring(loop))
    if not loops:
        return None
    return max(loops, key=polygon_area)


def parse_line_param(params: str) -> Optional[Tuple[Point2, Point2]]:
    values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", params)]
    if len(values) != 4:
        return None
    return (values[0], values[1]), (values[2], values[3])


def parse_points_param(params: str) -> Optional[Tuple[Point2, Point2]]:
    values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", params)]
    if len(values) != 4:
        return None
    return (values[0], values[1]), (values[2], values[3])


def line_value_at_x(line: Tuple[Point2, Point2], x: float) -> float:
    (x1, y1), (x2, y2) = line
    if abs(x2 - x1) < 1.0e-12:
        return min(y1, y2)
    t = (x - x1) / (x2 - x1)
    return y1 + (y2 - y1) * t


def clip_polygon_above_line(poly: Sequence[Point2], line: Tuple[Point2, Point2]) -> List[Point2]:
    if len(poly) < 3:
        return list(poly)

    def inside(point: Point2) -> bool:
        return point[1] >= line_value_at_x(line, point[0]) - 1.0e-9

    def intersection(start: Point2, end: Point2) -> Point2:
        x1, y1 = start
        x2, y2 = end
        (lx1, ly1), (lx2, ly2) = line
        dx = x2 - x1
        dy = y2 - y1
        ldx = lx2 - lx1
        ldy = ly2 - ly1
        denom = dx * ldy - dy * ldx
        if abs(denom) < 1.0e-12:
            return end
        t = ((lx1 - x1) * ldy - (ly1 - y1) * ldx) / denom
        return x1 + t * dx, y1 + t * dy

    output: List[Point2] = []
    previous = poly[-1]
    previous_inside = inside(previous)
    for current in poly:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                output.append(intersection(previous, current))
            output.append(current)
        elif previous_inside:
            output.append(intersection(previous, current))
        previous = current
        previous_inside = current_inside
    return simplify_ring(output) if len(output) >= 3 else list(poly)


def replace_south_boundary_with_line(poly: Sequence[Point2], line: Tuple[Point2, Point2]) -> List[Point2]:
    """Rebuild an x-monotone polygon so the supplied line is its full south edge."""
    if len(poly) < 3:
        return list(poly)
    (line_x1, _), (line_x2, _) = line
    if abs(line_x2 - line_x1) < 1.0e-12:
        return clip_polygon_above_line(poly, line)

    xs = sorted({round(x, 10) for x, _ in poly})
    if len(xs) < 2:
        return list(poly)

    upper_chain: List[Point2] = []

    def append_distinct(point: Point2) -> None:
        if not upper_chain or abs(upper_chain[-1][0] - point[0]) > 1.0e-9 or abs(upper_chain[-1][1] - point[1]) > 1.0e-9:
            upper_chain.append(point)

    for x0, x1 in zip(xs, xs[1:]):
        if x1 - x0 <= 1.0e-10:
            continue
        sample_x = (x0 + x1) * 0.5
        candidates: List[Tuple[float, Point2, Point2]] = []
        for index, start in enumerate(poly):
            end = poly[(index + 1) % len(poly)]
            dx = end[0] - start[0]
            if abs(dx) < 1.0e-12:
                continue
            if min(start[0], end[0]) - 1.0e-9 <= sample_x <= max(start[0], end[0]) + 1.0e-9:
                t = (sample_x - start[0]) / dx
                y = start[1] + t * (end[1] - start[1])
                candidates.append((y, start, end))
        if not candidates:
            return clip_polygon_above_line(poly, line)
        _, start, end = max(candidates, key=lambda item: item[0])
        dx = end[0] - start[0]
        y0 = start[1] + (x0 - start[0]) / dx * (end[1] - start[1])
        y1 = start[1] + (x1 - start[0]) / dx * (end[1] - start[1])
        append_distinct((x0, y0))
        append_distinct((x1, y1))

    if len(upper_chain) < 2:
        return clip_polygon_above_line(poly, line)
    if any(line_value_at_x(line, x) > y + 1.0e-9 for x, y in upper_chain):
        return clip_polygon_above_line(poly, line)

    xmin, xmax = xs[0], xs[-1]
    south_west = (xmin, line_value_at_x(line, xmin))
    south_east = (xmax, line_value_at_x(line, xmax))
    return simplify_ring([south_west, south_east, *reversed(upper_chain)])


def parse_zone_footprints(path: Path) -> Dict[str, ZoneShape]:
    zones: Dict[str, List[List[Point2]]] = {}
    for fields in idf_objects(read_text(path)):
        if fields[0].lower() != "buildingsurface:detailed":
            continue
        if len(fields) < 12 or fields[2].lower() != "floor":
            continue
        zone_name = fields[4]
        vertices = vertices_from_fields(fields, 10)
        poly = [(x, y) for x, y, _ in vertices]
        zones.setdefault(zone_name, []).append(poly)
    result: Dict[str, ZoneShape] = {}
    for zone_name, polys in zones.items():
        poly = max(polys, key=polygon_area)
        result[zone_name] = ZoneShape(zone_name, poly)
    return dict(sorted(result.items(), key=lambda item: zone_sort_key(item[0])))


def zone_sort_key(name: str) -> Tuple[int, str]:
    digits = "".join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 9999, name)


def bbox(poly: Sequence[Point2]) -> Tuple[float, float, float, float]:
    xs = [x for x, _ in poly]
    ys = [y for _, y in poly]
    return min(xs), max(xs), min(ys), max(ys)


def split_shape(shape: ZoneShape, axis: str, position: float) -> Optional[Tuple[ZoneShape, ZoneShape]]:
    xmin, xmax, ymin, ymax = bbox(shape.polygon)
    if axis == "x":
        if not xmin < position < xmax:
            return None
        west = ZoneShape(f"{shape.name}_west", [(xmin, ymin), (position, ymin), (position, ymax), (xmin, ymax)], "split")
        east = ZoneShape(f"{shape.name}_east", [(position, ymin), (xmax, ymin), (xmax, ymax), (position, ymax)], "split")
        return west, east
    if axis == "y":
        if not ymin < position < ymax:
            return None
        south = ZoneShape(f"{shape.name}_south", [(xmin, ymin), (xmax, ymin), (xmax, position), (xmin, position)], "split")
        north = ZoneShape(f"{shape.name}_north", [(xmin, position), (xmax, position), (xmax, ymax), (xmin, ymax)], "split")
        return south, north
    return None


def split_axis_value(text: str) -> str:
    value = text.strip().lower()
    if value.startswith("x"):
        return "x"
    if value.startswith("y"):
        return "y"
    return value


def split_axis_label(axis: str) -> str:
    if axis == "x":
        return "x: vertical cut (from west wall)"
    if axis == "y":
        return "y: horizontal cut (from south wall)"
    return axis


def split_axis_hint(shape: ZoneShape, axis: str, position: float) -> str:
    xmin, xmax, ymin, ymax = bbox(shape.polygon)
    other_axis = "y" if axis == "x" else "x"
    other_ok = split_shape(shape, other_axis, position) is not None
    ranges = f"x range {xmin:g}-{xmax:g}, y range {ymin:g}-{ymax:g}"
    if other_ok:
        return f"{axis}={position:g} is outside the valid cut range for this zone ({ranges}).The value is valid as {other_axis}={position:g} instead; check whether the wrong axis was selected."
    return f"{axis}={position:g} is outside the valid cut range for this zone ({ranges})."


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_idf_toolkit() -> ModuleType:
    global _IDF_TOOLKIT
    if _IDF_TOOLKIT is not None:
        return _IDF_TOOLKIT
    if not TOOLKIT_PY.exists():
        raise FileNotFoundError(f"Underlying IDF tool not found: {TOOLKIT_PY}")
    module_name = "_gui_idf_toolkit"
    spec = importlib.util.spec_from_file_location(module_name, str(TOOLKIT_PY))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load underlying IDF tool: {TOOLKIT_PY}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _IDF_TOOLKIT = module
    return module


def clockwise_polygon(poly: Sequence[Point2]) -> List[Point2]:
    result = simplify_ring(list(poly))
    if len(result) >= 3 and signed_polygon_area(result) > 0:
        result = list(reversed(result))
    return result


def display_label(name: str) -> str:
    label = re.sub(r"[^0-9A-Za-z_\-]+", "_", name).strip("_")
    return label or "zone"


def source_base_name(name: str) -> str:
    base = re.sub(r"-\d+$", "", name)
    for suffix in ("_west", "_east", "_south", "_north"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


class IdFGuiPostprocessor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("IDF Geometry Post-Processing Tool")
        self.root.geometry("1180x780")
        self.root.minsize(1040, 680)
        self.root.bind("<Control-Return>", lambda _event: self.execute())
        self.root.bind("<Control-z>", lambda _event: self.undo_operation())
        self.input_idf: Optional[Path] = None
        self.original_shapes: Dict[str, ZoneShape] = {}
        self.current_shapes: Dict[str, ZoneShape] = {}
        self.selected_zones: List[str] = []
        self.operations: List[GuiOperation] = []
        self.canvas_items: Dict[str, int] = {}
        self.canvas_texts: Dict[str, int] = {}
        self.scale = 1.0
        self.min_x = self.max_x = self.min_y = self.max_y = 0.0

        self.operation_var = tk.StringVar(value="split")
        self.axis_var = tk.StringVar(value=split_axis_label("x"))
        self.position_var = tk.StringVar()
        self.merge_output_var = tk.StringVar()
        self.trim_output_var = tk.StringVar()
        self.trim_mode_var = tk.StringVar(value="line")
        self.trim_param_var = tk.StringVar()
        self.map_output_var = tk.StringVar()

        self._build_layout()
        self.refresh_input()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, padding=10)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        top = ttk.Frame(left)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Input IDF: ").grid(row=0, column=0, sticky="w")
        self.input_label = ttk.Label(top, text="Scanning input...", foreground="#334155")
        self.input_label.grid(row=0, column=1, sticky="w")
        ttk.Button(top, text="Rescan", command=self.refresh_input).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(top, text="Clear selection", command=self.clear_selection).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(top, text="Validate and Export", command=self.execute).grid(row=0, column=4, padx=(8, 0))

        self.canvas = tk.Canvas(left, background="#f8fafc", highlightthickness=1, highlightbackground="#cbd5e1")
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self.redraw())

        right = ttk.Frame(self.root, padding=10)
        right.grid(row=0, column=1, sticky="ns")
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Available zones").grid(row=0, column=0, sticky="w")
        self.zone_list = tk.Listbox(right, selectmode=tk.EXTENDED, height=12, exportselection=False)
        self.zone_list.grid(row=1, column=0, sticky="ew")
        self.zone_list.bind("<<ListboxSelect>>", lambda _event: self.select_from_list())

        ttk.Label(right, text="Selected zones").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.selection_label = ttk.Label(right, text="None", foreground="#0f172a", wraplength=340)
        self.selection_label.grid(row=3, column=0, sticky="ew")

        op_box = ttk.LabelFrame(right, text="Add operation", padding=8)
        op_box.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        op_box.columnconfigure(1, weight=1)

        ttk.Label(op_box, text="Operation type").grid(row=0, column=0, sticky="w")
        op_combo = ttk.Combobox(
            op_box,
            textvariable=self.operation_var,
            values=["split", "merge", "trim_merge", "map"],
            state="readonly",
            width=18,
        )
        op_combo.grid(row=0, column=1, sticky="ew")
        op_combo.bind("<<ComboboxSelected>>", lambda _event: (self.update_operation_form(), self.suggest_form_defaults()))

        self.form_frame = ttk.Frame(op_box)
        self.form_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.form_frame.columnconfigure(1, weight=1)
        ttk.Button(op_box, text="Add to queue", command=self.add_operation).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        ttk.Label(right, text="Operation queue").grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.operation_list = tk.Listbox(right, height=13, exportselection=False)
        self.operation_list.configure(selectmode=tk.EXTENDED)
        self.operation_list.grid(row=6, column=0, sticky="ew")
        self.operation_list.bind("<Delete>", lambda _event: self.delete_selected_operations())

        action_bar = ttk.Frame(right)
        action_bar.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        action_bar.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(action_bar, text="Delete selected", command=self.delete_selected_operations).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(action_bar, text="Undo last", command=self.undo_operation).grid(row=0, column=1, sticky="ew", padx=(3, 3))
        ttk.Button(action_bar, text="Clear queue", command=self.clear_operations).grid(row=0, column=2, sticky="ew", padx=(3, 0))

        ttk.Button(right, text="Validate and Export", command=self.execute).grid(row=8, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(right, text="Show restoration recipe", command=self.show_recipe_help).grid(row=9, column=0, sticky="ew", pady=(6, 0))

        ttk.Label(right, text="Shortcuts: Ctrl+Enter export, Ctrl+Z undo", foreground="#64748b").grid(row=10, column=0, sticky="ew", pady=(8, 0))
        self.status_label = ttk.Label(right, text="", wraplength=340, foreground="#475569")
        self.status_label.grid(row=11, column=0, sticky="ew", pady=(10, 0))
        self.update_operation_form()

    def update_operation_form(self) -> None:
        for child in self.form_frame.winfo_children():
            child.destroy()
        kind = self.operation_var.get()
        if kind == "split":
            ttk.Label(self.form_frame, text="Axis").grid(row=0, column=0, sticky="w")
            ttk.Combobox(
                self.form_frame,
                textvariable=self.axis_var,
                values=[split_axis_label("x"), split_axis_label("y")],
                state="readonly",
                width=18,
            ).grid(row=0, column=1, sticky="ew")
            ttk.Label(self.form_frame, text="Position").grid(row=1, column=0, sticky="w", pady=(6, 0))
            ttk.Entry(self.form_frame, textvariable=self.position_var).grid(row=1, column=1, sticky="ew", pady=(6, 0))
            ttk.Label(self.form_frame, text="Restoration batch 1 uses vertical x cuts", foreground="#64748b").grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        elif kind == "merge":
            ttk.Label(self.form_frame, text="Output zone name").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.form_frame, textvariable=self.merge_output_var).grid(row=0, column=1, sticky="ew")
        elif kind == "trim_merge":
            ttk.Label(self.form_frame, text="Output zone name").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.form_frame, textvariable=self.trim_output_var).grid(row=0, column=1, sticky="ew")
            ttk.Label(self.form_frame, text="Parameter mode").grid(row=1, column=0, sticky="w", pady=(6, 0))
            trim_mode_combo = ttk.Combobox(self.form_frame, textvariable=self.trim_mode_var, values=["line", "points"], state="readonly", width=10)
            trim_mode_combo.grid(row=1, column=1, sticky="ew", pady=(6, 0))
            trim_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self.reset_trim_param_template())
            ttk.Label(self.form_frame, text="Parameters").grid(row=2, column=0, sticky="w", pady=(6, 0))
            ttk.Entry(self.form_frame, textvariable=self.trim_param_var).grid(row=2, column=1, sticky="ew", pady=(6, 0))
            self.reset_trim_param_template()
        elif kind == "map":
            ttk.Label(self.form_frame, text="Output zone name").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.form_frame, textvariable=self.map_output_var).grid(row=0, column=1, sticky="ew")

    def refresh_input(self) -> None:
        INPUT_DIR.mkdir(exist_ok=True)
        OUTPUT_DIR.mkdir(exist_ok=True)
        RECORDS_DIR.mkdir(exist_ok=True)
        idfs = sorted(INPUT_DIR.glob("*.idf"))
        if not idfs:
            self.input_label.config(text="No IDF file in input")
            messagebox.showwarning("IDF not found", f"Place the input IDF in: \n{INPUT_DIR}")
            return
        if len(idfs) > 1:
            self.input_label.config(text=f"Found {len(idfs)} IDF files in input")
            messagebox.showwarning("Too many IDF files", "Keep exactly one IDF file in the input directory. Remove extras and rescan.")
            return
        self.input_idf = idfs[0]
        try:
            self.original_shapes = parse_zone_footprints(self.input_idf)
        except Exception as exc:
            messagebox.showerror("Parse failed", f"Unable to parse IDF zones:\n{exc}")
            return
        self.current_shapes = {name: ZoneShape(shape.name, list(shape.polygon), shape.source, shape.command_name) for name, shape in self.original_shapes.items()}
        self.operations.clear()
        self.selected_zones.clear()
        self.input_label.config(text=f"{self.input_idf.name}; {len(self.current_shapes)} zones detected")
        self.refresh_zone_list()
        self.refresh_operation_list()
        self.redraw()
        self.set_status("Input IDF loaded. Click a zone in the plan or select it from the list.")

    def refresh_zone_list(self) -> None:
        self.zone_list.delete(0, tk.END)
        for name in sorted(self.current_shapes, key=zone_sort_key):
            self.zone_list.insert(tk.END, name)

    def set_status(self, text: str) -> None:
        self.status_label.config(text=text)

    def transform_setup(self) -> None:
        if not self.current_shapes:
            return
        xs = [x for shape in self.current_shapes.values() for x, _ in shape.polygon]
        ys = [y for shape in self.current_shapes.values() for _, y in shape.polygon]
        self.min_x, self.max_x = min(xs), max(xs)
        self.min_y, self.max_y = min(ys), max(ys)
        width = max(self.canvas.winfo_width(), 400)
        height = max(self.canvas.winfo_height(), 400)
        span_x = max(self.max_x - self.min_x, 1.0)
        span_y = max(self.max_y - self.min_y, 1.0)
        self.scale = min((width - 60) / span_x, (height - 60) / span_y)

    def to_canvas(self, point: Point2) -> Point2:
        width = max(self.canvas.winfo_width(), 400)
        height = max(self.canvas.winfo_height(), 400)
        x, y = point
        sx = 30 + (x - self.min_x) * self.scale
        sy = height - 30 - (y - self.min_y) * self.scale
        return sx, sy

    def redraw(self) -> None:
        self.canvas.delete("all")
        self.canvas_items.clear()
        self.canvas_texts.clear()
        if not self.current_shapes:
            return
        self.transform_setup()
        for name, shape in sorted(self.current_shapes.items(), key=lambda item: zone_sort_key(item[0])):
            points: List[float] = []
            for point in shape.polygon:
                sx, sy = self.to_canvas(point)
                points.extend([sx, sy])
            fill = "#f97316" if name in self.selected_zones else "#f8a05f"
            outline = "#111827" if name in self.selected_zones else "#334155"
            width = 3 if name in self.selected_zones else 1
            item = self.canvas.create_polygon(points, fill=fill, outline=outline, width=width, tags=(f"zone:{name}",))
            cx, cy = self.to_canvas(polygon_centroid(shape.polygon))
            text = self.canvas.create_text(cx, cy, text=name, fill="#111827", font=("Arial", 10, "bold"), tags=(f"zone:{name}",))
            self.canvas.tag_bind(f"zone:{name}", "<Button-1>", lambda _event, zone=name: self.toggle_zone(zone))
            self.canvas_items[name] = item
            self.canvas_texts[name] = text

    def toggle_zone(self, zone: str) -> None:
        if zone in self.selected_zones:
            self.selected_zones.remove(zone)
        else:
            self.selected_zones.append(zone)
        self.sync_list_selection()
        self.refresh_selection_label()
        self.suggest_form_defaults()
        self.redraw()

    def select_from_list(self) -> None:
        self.selected_zones = [self.zone_list.get(index) for index in self.zone_list.curselection()]
        self.refresh_selection_label()
        self.suggest_form_defaults()
        self.redraw()

    def sync_list_selection(self) -> None:
        self.zone_list.selection_clear(0, tk.END)
        names = [self.zone_list.get(index) for index in range(self.zone_list.size())]
        for zone in self.selected_zones:
            if zone in names:
                self.zone_list.selection_set(names.index(zone))

    def clear_selection(self) -> None:
        self.selected_zones.clear()
        self.zone_list.selection_clear(0, tk.END)
        self.refresh_selection_label()
        self.redraw()

    def refresh_selection_label(self) -> None:
        self.selection_label.config(text=", ".join(self.selected_zones) if self.selected_zones else "None")

    def reset_trim_param_template(self) -> None:
        template = POINTS_PARAM_TEMPLATE if self.trim_mode_var.get() == "points" else LINE_PARAM_TEMPLATE
        self.trim_param_var.set(template)

    def suggest_form_defaults(self) -> None:
        if not self.selected_zones:
            return
        command_set = frozenset(self.command_names(self.selected_zones))
        kind = self.operation_var.get()
        if kind == "merge":
            output = RESTORE_MERGE_DEFAULT_OUTPUTS.get(command_set)
            if output:
                self.merge_output_var.set(output)
        elif kind == "trim_merge":
            defaults = RESTORE_TRIM_DEFAULTS.get(command_set)
            if defaults:
                output, mode, params = defaults
                self.trim_output_var.set(output)
                self.trim_mode_var.set(mode)
                self.trim_param_var.set(params)
        elif kind == "map" and len(self.selected_zones) == 1:
            output = RESTORE_MAP_DEFAULT_OUTPUTS.get(self.command_name(self.selected_zones[0]))
            if output:
                self.map_output_var.set(output)

    def command_name(self, display_name: str) -> str:
        shape = self.current_shapes.get(display_name)
        return shape.command_name if shape else display_name

    def command_names(self, display_names: Sequence[str]) -> List[str]:
        return [self.command_name(name) for name in display_names]

    def unique_display_name(self, desired: str, selected_display_names: Sequence[str]) -> Tuple[str, Optional[str]]:
        if desired not in self.current_shapes or desired in selected_display_names:
            return desired, None
        suffix = 1
        while f"{desired}-{suffix}" in self.current_shapes:
            suffix += 1
        return f"{desired}-{suffix}", f"Output name {desired} already exists. It is displayed as {desired}-{suffix}; the operation record retains -> {desired}."

    def add_operation(self) -> None:
        if not self.selected_zones:
            messagebox.showwarning("No zone selected", "Select a zone in the plan or zone list first.")
            return
        kind = self.operation_var.get()
        try:
            if kind == "split":
                self.add_split_operations()
            elif kind == "merge":
                self.add_merge_operation()
            elif kind == "trim_merge":
                self.add_trim_merge_operation()
            elif kind == "map":
                self.add_map_operation()
        except ValueError as exc:
            messagebox.showwarning("Invalid parameters", str(exc))

    def add_split_operations(self) -> None:
        axis = split_axis_value(self.axis_var.get())
        if axis not in {"x", "y"}:
            raise ValueError("The split axis must be x or y.")
        try:
            position = float(self.position_var.get())
        except ValueError as exc:
            raise ValueError("The split position must be numeric.") from exc
        planned: List[Tuple[str, str, Tuple[ZoneShape, ZoneShape]]] = []
        for zone in list(self.selected_zones):
            command_zone = self.command_name(zone)
            raw = f"split {command_zone} {axis}={position:g}"
            shape = self.current_shapes.get(zone)
            if shape:
                command_shape = ZoneShape(command_zone, shape.polygon, shape.source, command_zone)
                pieces = split_shape(command_shape, axis, position)
                if pieces is None:
                    raise ValueError(f"{split_axis_hint(command_shape, axis, position)}\nZone: {zone}")
                planned.append((zone, raw, pieces))
        for zone, raw, pieces in planned:
            self.operations.append(GuiOperation(raw, "split", [zone], f"{zone} split at {axis}={position:g}"))
            self.current_shapes.pop(zone, None)
            self.current_shapes[pieces[0].name] = pieces[0]
            self.current_shapes[pieces[1].name] = pieces[1]
        self.clear_selection()
        self.refresh_zone_list()
        self.refresh_operation_list()
        self.redraw()
        self.set_status("Split added. Generated child zones can be selected from the zone list.")

    def add_merge_operation(self) -> None:
        if len(self.selected_zones) < 2:
            raise ValueError("A merge requires at least two zones.")
        output = self.merge_output_var.get().strip() or self.selected_zones[0]
        selected_commands = RESTORE_MERGE_ORDER.get(frozenset(self.command_names(self.selected_zones)), self.command_names(self.selected_zones))
        selected_display = self.display_order_for_commands(selected_commands, self.selected_zones)
        display_output, conflict_note = self.unique_display_name(output, selected_display)
        raw = f"merge {'+'.join(selected_commands)} -> {output}"
        note = f"{' + '.join(selected_display)} merged into {output}"
        if conflict_note:
            note += f"; {conflict_note}"
        self.operations.append(GuiOperation(raw, "merge", list(selected_display), note))
        self.current_shapes[display_output] = self.merged_placeholder(display_output, selected_display, output)
        for zone in selected_display:
            if zone != display_output:
                self.current_shapes.pop(zone, None)
        self.clear_selection()
        self.refresh_zone_list()
        self.refresh_operation_list()
        self.redraw()
        self.set_status(conflict_note or "Merge added. Complex unions are previewed by their polygon boundary; the exported IDF is authoritative.")

    def display_order_for_commands(self, command_order: Sequence[str], selected_display: Sequence[str]) -> List[str]:
        display_by_command = {self.command_name(name): name for name in selected_display}
        return [display_by_command.get(command, command) for command in command_order]

    def merged_placeholder(self, output: str, zones: Sequence[str], command_output: Optional[str] = None) -> ZoneShape:
        polys = [self.current_shapes[zone].polygon for zone in zones if zone in self.current_shapes]
        if not polys:
            return ZoneShape(output, [(0, 0), (1, 0), (1, 1), (0, 1)], "merged", command_output or output)
        outline = polygon_union_outline(polys)
        if outline:
            return ZoneShape(output, outline, "merged", command_output or output)
        xs = [x for poly in polys for x, _ in poly]
        ys = [y for poly in polys for _, y in poly]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        return ZoneShape(output, [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)], "merged", command_output or output)

    def trimmed_placeholder(
        self,
        output: str,
        zones: Sequence[str],
        mode: str,
        params: str,
        command_output: Optional[str] = None,
    ) -> ZoneShape:
        shape = self.merged_placeholder(output, zones, command_output)
        if mode == "line":
            line = parse_line_param(params)
            if line:
                shape.polygon = replace_south_boundary_with_line(shape.polygon, line)
        return shape

    def add_trim_merge_operation(self) -> None:
        if len(self.selected_zones) < 2:
            raise ValueError("A trimmed merge requires at least two zones.")
        output = self.trim_output_var.get().strip()
        if not output:
            raise ValueError("Enter an output zone name.")
        mode = self.trim_mode_var.get().strip()
        params = self.trim_param_var.get().strip()
        if mode not in {"line", "points"}:
            raise ValueError("Parameter mode must be line or points.")
        if mode == "line" and parse_line_param(params) is None:
            raise ValueError("Complete the line parameter as (x1,y1)-(x2,y2).")
        if mode == "points" and parse_points_param(params) is None:
            raise ValueError("Complete the points parameter as (x1,y1),(x2,y2).")
        selected_commands = RESTORE_TRIM_ORDER.get(frozenset(self.command_names(self.selected_zones)), self.command_names(self.selected_zones))
        selected_display = self.display_order_for_commands(selected_commands, self.selected_zones)
        display_output, conflict_note = self.unique_display_name(output, selected_display)
        raw = f"trim_merge {'+'.join(selected_commands)} -> {output} {mode}={params}"
        note = f"{' + '.join(selected_display)} trim-merged into {output}"
        if conflict_note:
            note += f"; {conflict_note}"
        self.operations.append(GuiOperation(raw, "trim_merge", list(selected_display), note))
        self.current_shapes[display_output] = self.trimmed_placeholder(display_output, selected_display, mode, params, output)
        for zone in selected_display:
            if zone != display_output:
                self.current_shapes.pop(zone, None)
        self.clear_selection()
        self.reset_trim_param_template()
        self.refresh_zone_list()
        self.refresh_operation_list()
        self.redraw()
        self.set_status(conflict_note or "Trimmed merge added.")

    def add_map_operation(self) -> None:
        if len(self.selected_zones) != 1:
            raise ValueError("A map operation accepts exactly one zone.")
        output = self.map_output_var.get().strip()
        if not output:
            raise ValueError("Enter an output zone name.")
        source = self.selected_zones[0]
        command_source = self.command_name(source)
        display_output, conflict_note = self.unique_display_name(output, [source])
        raw = f"map {command_source} -> {output}"
        note = f"{source} mapped directly to {output}"
        if conflict_note:
            note += f"; {conflict_note}"
        self.operations.append(GuiOperation(raw, "map", [source], note))
        if source in self.current_shapes:
            shape = self.current_shapes.pop(source)
            shape.name = display_output
            shape.command_name = output
            shape.source = "mapped"
            self.current_shapes[display_output] = shape
        self.clear_selection()
        self.refresh_zone_list()
        self.refresh_operation_list()
        self.redraw()
        self.set_status(conflict_note or "Direct map added.")

    def refresh_operation_list(self) -> None:
        self.operation_list.delete(0, tk.END)
        for index, operation in enumerate(self.operations, 1):
            self.operation_list.insert(tk.END, f"{index:02d}. {operation.raw}")

    def undo_operation(self) -> None:
        if self.operation_list.curselection():
            self.delete_selected_operations()
            return
        if not self.operations:
            return
        self.operations.pop()
        self.rebuild_current_shapes_from_operations()
        self.refresh_operation_list()
        self.set_status("Last operation undone.")

    def delete_selected_operations(self) -> None:
        selected = sorted(self.operation_list.curselection(), reverse=True)
        if not selected:
            return
        for index in selected:
            if 0 <= index < len(self.operations):
                self.operations.pop(index)
        self.rebuild_current_shapes_from_operations()
        self.refresh_operation_list()
        self.set_status(f"Deleted {len(selected)} selected operations.")

    def clear_operations(self) -> None:
        if not self.operations:
            return
        if not messagebox.askyesno("Confirm clear", "Clear all operations?"):
            return
        self.operations.clear()
        self.rebuild_current_shapes_from_operations()
        self.refresh_operation_list()
        self.set_status("Operation queue cleared.")

    def rebuild_current_shapes_from_operations(self) -> None:
        self.current_shapes = {name: ZoneShape(shape.name, list(shape.polygon), shape.source, shape.command_name) for name, shape in self.original_shapes.items()}
        ops = list(self.operations)
        self.operations = []
        saved_selection = list(self.selected_zones)
        self.selected_zones = []
        for operation in ops:
            self.apply_operation_to_shape_state(operation)
            self.operations.append(operation)
        self.selected_zones = [zone for zone in saved_selection if zone in self.current_shapes]
        self.refresh_zone_list()
        self.sync_list_selection()
        self.refresh_selection_label()
        self.redraw()

    def apply_operation_to_shape_state(self, operation: GuiOperation) -> None:
        if operation.kind == "split":
            parts = operation.raw.split()
            zone = operation.selected_zones[0] if operation.selected_zones else operation.raw.split()[1]
            axis, value = parts[2].split("=", 1)
            shape = self.current_shapes.get(zone)
            if shape:
                pieces = split_shape(ZoneShape(shape.command_name, shape.polygon, shape.source, shape.command_name), axis, float(value))
                if pieces:
                    self.current_shapes.pop(zone, None)
                    self.current_shapes[pieces[0].name] = pieces[0]
                    self.current_shapes[pieces[1].name] = pieces[1]
        elif operation.kind in {"merge", "trim_merge"}:
            selected = operation.selected_zones
            output = operation.raw.split("->", 1)[1].strip().split()[0]
            display_output, _ = self.unique_display_name(output, selected)
            if operation.kind == "trim_merge":
                tail = operation.raw.split("->", 1)[1]
                if " line=" in tail:
                    params = tail.split(" line=", 1)[1].strip()
                    self.current_shapes[display_output] = self.trimmed_placeholder(display_output, selected, "line", params, output)
                elif " points=" in tail:
                    params = tail.split(" points=", 1)[1].strip()
                    self.current_shapes[display_output] = self.trimmed_placeholder(display_output, selected, "points", params, output)
                else:
                    self.current_shapes[display_output] = self.merged_placeholder(display_output, selected, output)
            else:
                self.current_shapes[display_output] = self.merged_placeholder(display_output, selected, output)
            for zone in selected:
                if zone != display_output:
                    self.current_shapes.pop(zone, None)
        elif operation.kind == "map":
            source = operation.selected_zones[0]
            output = operation.raw.split("->", 1)[1].strip().split()[0]
            if source in self.current_shapes:
                display_output, _ = self.unique_display_name(output, [source])
                shape = self.current_shapes.pop(source)
                shape.name = display_output
                shape.command_name = output
                self.current_shapes[display_output] = shape

    def ask_continue_output(
        self,
        title: str,
        message: str,
        continue_text: str = "Continue export",
        cancel_text: str = "Return to edit",
    ) -> bool:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill=tk.BOTH, expand=True)
        label = ttk.Label(frame, text=message, wraplength=660, justify=tk.LEFT)
        label.pack(fill=tk.BOTH, expand=True)

        result = {"value": False}

        def close(value: bool) -> None:
            result["value"] = value
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(buttons, text=cancel_text, command=lambda: close(False)).pack(side=tk.RIGHT)
        ttk.Button(buttons, text=continue_text, command=lambda: close(True)).pack(side=tk.RIGHT, padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_width()) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.focus_set()
        self.root.wait_window(dialog)
        return result["value"]

    def execute(self) -> None:
        if self.input_idf is None:
            messagebox.showwarning("No input", "Load the IDF from the input directory first.")
            return
        errors, warnings = self.validate_operations()
        if errors:
            messagebox.showerror("Validation failed", "The following issues were found: \n\n" + "\n".join(errors[:12]))
            return
        if warnings:
            message = "Validation passed with the following warnings: \n\n" + "\n".join(warnings[:12])
            if len(warnings) > 12:
                message += f"\n... {len(warnings) - 12} additional warnings"
            message += "\n\nContinue exporting?"
            if not self.ask_continue_output("Validation warnings", message):
                return
        raw_ops = [operation.raw for operation in self.operations]
        check_ops = [CheckOperation(raw) for raw in raw_ops]
        known_restore = is_restore13_stepwise_recipe(check_ops)  # type: ignore[arg-type]
        restore_status = restore13_stepwise_status(check_ops)  # type: ignore[arg-type]
        entered_canonical = {canonical_command(raw) for raw in raw_ops}
        restore_overlap = sum(1 for command in RESTORE13_STEPWISE_COMMANDS if canonical_command(command) in entered_canonical)
        restore_hint = ""
        if not known_restore and restore_overlap >= 4:
            restore_hint = "Note: the current operation queue does not exactly match the built-in 13-zone restoration recipe."
            if restore_status["missing"]:
                restore_hint += "\n\nMissing commands: \n" + "\n".join(restore_status["missing"][:10])
                if len(restore_status["missing"]) > 10:
                    restore_hint += f"\n... {len(restore_status['missing']) - 10} additional items"
            if restore_status["extra"]:
                restore_hint += "\n\nMismatched or extra commands: \n" + "\n".join(restore_status["extra"][:10])
                if len(restore_status["extra"]) > 10:
                    restore_hint += f"\n... {len(restore_status['extra']) - 10} additional items"
            restore_hint += "\n\nThis recipe notice is not a general export restriction. If general validation has no errors, the current queue can still be exported."
        confirm_text = "Validation passed. Export now?"
        if known_restore:
            confirm_text = "Validation passed and the verified 13-zone restoration sequence was detected. Generate the final IDF?"
        else:
            confirm_text = (
                "Validation passed. The current sequence is not the built-in 13-zone restoration recipe.\n\n"
                "The program will rebuild the IDF from the current GUI geometry and export an operation record and SVG preview.\n\n"
                "Continue exporting?"
            )
            if restore_hint:
                confirm_text = restore_hint + "\n\n" + confirm_text
        if not self.ask_continue_output("Confirm export", confirm_text):
            return
        paths = self.output_paths()
        if known_restore:
            code, stdout, stderr = self.run_restore13(paths)
            self.write_session_record(paths, code, stdout, stderr, warnings)
            if code != 0:
                messagebox.showerror("Processing failed", f"Exit code: {code}\n\n{stderr or stdout}")
                return
            report_text = self.report_summary(paths["report"])
            messagebox.showinfo("Processing complete", f"Output IDF: \n{paths['idf']}\n\n{report_text}")
        else:
            self.write_generic_outputs(paths, warnings)
            self.write_session_record(paths, 0, "generic geometry executed", "", warnings)
            messagebox.showinfo(
                "Processing complete",
                f"IDF rebuilt from the current GUI queue: \n{paths['idf']}\n\nOperation record and preview: \n{paths['operations']}\n{paths['svg']}",
            )
        self.set_status(f"Processing complete: {paths['idf'].name}")

    def validate_operations(self) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        if not self.operations:
            return ["The operation queue is empty. Add at least one operation."], warnings
        seen: Dict[str, int] = {}
        shapes = {name: ZoneShape(shape.name, list(shape.polygon), shape.source, shape.command_name) for name, shape in self.original_shapes.items()}

        def unique_name(desired: str, selected: Sequence[str]) -> Tuple[str, Optional[str]]:
            if desired not in shapes or desired in selected:
                return desired, None
            suffix = 1
            while f"{desired}-{suffix}" in shapes:
                suffix += 1
            return f"{desired}-{suffix}", f"Output name {desired} already exists and will be displayed as {desired}-{suffix}."

        for index, operation in enumerate(self.operations, 1):
            canonical = canonical_command(operation.raw)
            seen[canonical] = seen.get(canonical, 0) + 1
            if seen[canonical] > 1:
                warnings.append(f"Step {index} duplicates an earlier operation: {operation.raw}")
            missing = [zone for zone in operation.selected_zones if zone not in shapes]
            if missing:
                errors.append(f"Step {index} references zones that do not currently exist: {', '.join(missing)}")
                continue
            try:
                if operation.kind == "split":
                    parts = operation.raw.split()
                    if len(parts) < 3 or "=" not in parts[2]:
                        errors.append(f"Step {index} has invalid split syntax: {operation.raw}")
                        continue
                    zone = operation.selected_zones[0]
                    axis, value = parts[2].split("=", 1)
                    position = float(value)
                    pieces = split_shape(shapes[zone], axis, position)
                    if pieces is None:
                        errors.append(f"Step {index}: {split_axis_hint(shapes[zone], axis, position)} Zone: {zone}")
                        continue
                    shapes.pop(zone, None)
                    shapes[pieces[0].name] = pieces[0]
                    shapes[pieces[1].name] = pieces[1]
                elif operation.kind in {"merge", "trim_merge"}:
                    if len(operation.selected_zones) < 2:
                        errors.append(f"Step {index} requires at least two zones: {operation.raw}")
                        continue
                    if "->" not in operation.raw:
                        errors.append(f"Step {index} is missing an output zone name: {operation.raw}")
                        continue
                    output = operation.raw.split("->", 1)[1].strip().split()[0]
                    display_output, note = unique_name(output, operation.selected_zones)
                    if note:
                        warnings.append(f"Step {index}: {note}")
                    if operation.kind == "trim_merge":
                        tail = operation.raw.split("->", 1)[1]
                        if " line=" in tail:
                            params = tail.split(" line=", 1)[1].strip()
                            shapes[display_output] = self.placeholder_from_shapes(display_output, operation.selected_zones, shapes, output, "line", params)
                        elif " points=" in tail:
                            params = tail.split(" points=", 1)[1].strip()
                            shapes[display_output] = self.placeholder_from_shapes(display_output, operation.selected_zones, shapes, output, "points", params)
                        else:
                            shapes[display_output] = self.placeholder_from_shapes(display_output, operation.selected_zones, shapes, output)
                    else:
                        shapes[display_output] = self.placeholder_from_shapes(display_output, operation.selected_zones, shapes, output)
                    for zone in operation.selected_zones:
                        if zone != display_output:
                            shapes.pop(zone, None)
                elif operation.kind == "map":
                    if len(operation.selected_zones) != 1:
                        errors.append(f"Step {index} map must select exactly one zone: {operation.raw}")
                        continue
                    if "->" not in operation.raw:
                        errors.append(f"Step {index} is missing an output zone name: {operation.raw}")
                        continue
                    source = operation.selected_zones[0]
                    output = operation.raw.split("->", 1)[1].strip().split()[0]
                    display_output, note = unique_name(output, [source])
                    if note:
                        warnings.append(f"Step {index}: {note}")
                    shape = shapes.pop(source)
                    shape.name = display_output
                    shape.command_name = output
                    shapes[display_output] = shape
                else:
                    errors.append(f"Step {index} has an unrecognized operation type: {operation.raw}")
            except Exception as exc:
                errors.append(f"Step {index}validation failed: {operation.raw}; Reason: {exc}")
        return errors, warnings

    def placeholder_from_shapes(
        self,
        output: str,
        zones: Sequence[str],
        shapes: Dict[str, ZoneShape],
        command_output: Optional[str] = None,
        mode: str = "",
        params: str = "",
    ) -> ZoneShape:
        polys = [shapes[zone].polygon for zone in zones if zone in shapes]
        if not polys:
            return ZoneShape(output, [(0, 0), (1, 0), (1, 1), (0, 1)], "merged", command_output or output)
        outline = polygon_union_outline(polys)
        if outline:
            if mode == "line":
                line = parse_line_param(params)
                if line:
                    outline = replace_south_boundary_with_line(outline, line)
            return ZoneShape(output, outline, "merged", command_output or output)
        xs = [x for poly in polys for x, _ in poly]
        ys = [y for poly in polys for _, y in poly]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        return ZoneShape(output, [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)], "merged", command_output or output)

    def output_paths(self) -> Dict[str, Path]:
        assert self.input_idf is not None
        stem = self.input_idf.stem
        return {
            "idf": OUTPUT_DIR / f"{stem}_processed.idf",
            "svg": OUTPUT_DIR / f"{stem}_processed.svg",
            "report": RECORDS_DIR / f"{stem}_report.json",
            "operations": RECORDS_DIR / f"{stem}_operations.json",
            "session": RECORDS_DIR / f"{stem}_gui_session_{now_stamp()}.json",
        }

    def run_restore13(self, paths: Dict[str, Path]) -> Tuple[int, str, str]:
        assert self.input_idf is not None
        command = [
            "cmd",
            "/c",
            str(TOOL_BAT),
            "restore13",
            "--input",
            str(self.input_idf),
            "--reference",
            str(REFERENCE_IDF),
            "--output",
            str(paths["idf"]),
            "--report",
            str(paths["report"]),
            "--operations",
            str(paths["operations"]),
            "--svg",
            str(paths["svg"]),
        ]
        completed = subprocess.run(command, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return completed.returncode, completed.stdout, completed.stderr

    def build_generic_geometry(self):
        assert self.input_idf is not None
        toolkit = load_idf_toolkit()
        _, input_surfaces, input_windows = toolkit.parse_geometry(self.input_idf)

        z_by_zone: Dict[str, Tuple[float, float]] = {}
        all_z: List[float] = []
        for surface in input_surfaces:
            zvals = [z for _, _, z in surface.vertices]
            if not zvals:
                continue
            all_z.extend(zvals)
            current = z_by_zone.get(surface.zone_name)
            zmin, zmax = min(zvals), max(zvals)
            if current is None:
                z_by_zone[surface.zone_name] = (zmin, zmax)
            else:
                z_by_zone[surface.zone_name] = (min(current[0], zmin), max(current[1], zmax))
        if not all_z:
            raise ValueError("The input IDF has no surface vertices from which a story height can be determined.")
        default_z = (min(all_z), max(all_z))

        target_zones = []
        for name, shape in sorted(self.current_shapes.items(), key=lambda item: zone_sort_key(item[0])):
            candidates = [
                name,
                shape.command_name,
                source_base_name(name),
                source_base_name(shape.command_name),
            ]
            zmin, zmax = default_z
            for candidate in candidates:
                if candidate in z_by_zone:
                    zmin, zmax = z_by_zone[candidate]
                    break
            polygon = clockwise_polygon(shape.polygon)
            if len(polygon) < 3 or polygon_area(polygon) <= 1.0e-9:
                raise ValueError(f"Zone {name} has an invalid polygon and cannot be written to the IDF.")
            target_zones.append(
                toolkit.TargetZone(
                    name,
                    source_base_name(shape.command_name or name),
                    display_label(name),
                    polygon,
                    zmin,
                    zmax,
                )
            )

        surfaces = toolkit.build_surfaces(target_zones)
        try:
            windows, dropped_window_names = toolkit.map_input_windows_to_reference_topology(input_surfaces, input_windows, surfaces)
        except Exception:
            windows, dropped_count = toolkit.assign_windows(input_windows, surfaces)
            dropped_window_names = [f"unassigned_{index + 1}" for index in range(dropped_count)]
        return toolkit, target_zones, surfaces, windows, dropped_window_names, len(input_windows)

    def write_generic_outputs(self, paths: Dict[str, Path], warnings: Sequence[str]) -> None:
        assert self.input_idf is not None
        toolkit, target_zones, surfaces, windows, dropped_window_names, input_window_count = self.build_generic_geometry()
        geometry = toolkit.render_geometry(target_zones, surfaces, windows)
        toolkit.write_with_template(self.input_idf, paths["idf"], geometry)
        operations_payload = {
            "mode": "generic_geometry_execution",
            "geometry_executed": True,
            "note": "The commands passed generic validation. The output IDF was rebuilt from the current GUI zone polygons.",
            "input_idf": str(self.input_idf),
            "output_idf": str(paths["idf"]),
            "warnings": list(warnings),
            "operations": [asdict(operation) for operation in self.operations],
        }
        paths["operations"].write_text(json.dumps(operations_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        report = {
            "mode": "generic_geometry_execution",
            "input_idf": str(self.input_idf),
            "output_idf": str(paths["idf"]),
            "operation_count": len(self.operations),
            "final_zones": len(target_zones),
            "building_surfaces": len(surfaces),
            "input_windows": input_window_count,
            "final_windows": len(windows),
            "dropped_windows": len(dropped_window_names),
            "dropped_window_names": dropped_window_names,
            "warnings": list(warnings),
            "geometry_executed": True,
        }
        paths["report"].write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        self.write_preview_svg(paths["svg"])

    def write_preview_svg(self, output: Path) -> None:
        shapes = self.current_shapes
        width, height, margin = 900, 900, 30
        if not shapes:
            output.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\" />", encoding="utf-8")
            return
        xs = [x for shape in shapes.values() for x, _ in shape.polygon]
        ys = [y for shape in shapes.values() for _, y in shape.polygon]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        scale = min((width - 2 * margin) / max(max_x - min_x, 1.0), (height - 2 * margin) / max(max_y - min_y, 1.0))

        def sx(x: float) -> float:
            return margin + (x - min_x) * scale

        def sy(y: float) -> float:
            return height - margin - (y - min_y) * scale

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#f8fafc"/>',
        ]
        for name, shape in sorted(shapes.items(), key=lambda item: zone_sort_key(item[0])):
            points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in shape.polygon)
            cx, cy = polygon_centroid(shape.polygon)
            lines.append(f'<polygon points="{points}" fill="#f8a05f" stroke="#334155" stroke-width="2"/>')
            lines.append(f'<text x="{sx(cx):.2f}" y="{sy(cy):.2f}" text-anchor="middle" dominant-baseline="middle" font-family="Arial" font-size="14" fill="#111827">{name}</text>')
        lines.append("</svg>")
        output.write_text("\n".join(lines), encoding="utf-8")

    def write_session_record(self, paths: Dict[str, Path], code: int, stdout: str, stderr: str, warnings: Sequence[str]) -> None:
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "input_idf": str(self.input_idf),
            "output_idf": str(paths["idf"]),
            "report": str(paths["report"]),
            "operations_record": str(paths["operations"]),
            "exit_code": code,
            "warnings": list(warnings),
            "operations_entered_by_gui": [asdict(operation) for operation in self.operations],
            "stdout": stdout,
            "stderr": stderr,
        }
        paths["session"].write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def report_summary(self, report_path: Path) -> str:
        if not report_path.exists():
            return "Report file not found."
        report = json.loads(report_path.read_text(encoding="utf-8"))
        keys = ["final_zones", "building_surfaces", "input_windows", "final_windows", "dropped_windows"]
        return "\n".join(f"{key}: {report.get(key)}" for key in keys if key in report)

    def show_recipe_help(self) -> None:
        messagebox.showinfo("Four restoration batches", "\n\n".join([
            "Batch 1: \n" + "; ".join(RESTORE13_STEPWISE_COMMANDS[:4]),
            "Batch 2: \n" + "; ".join(RESTORE13_STEPWISE_COMMANDS[4:9]),
            "Batch 3: \n" + "; ".join(RESTORE13_STEPWISE_COMMANDS[9:12]),
            "Batch 4: \n" + "; ".join(RESTORE13_STEPWISE_COMMANDS[12:]),
        ]))


def main() -> int:
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    RECORDS_DIR.mkdir(exist_ok=True)
    root = tk.Tk()
    try:
        IdFGuiPostprocessor(root)
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("Application error", str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
