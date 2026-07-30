# Oblique Footprint Cutting

`cut_idf.py` clips rectangular thermal-zone footprints with an oblique boundary and projects south-wall windows onto the resulting sloped wall.

## Behavior

- Reads zone footprints, heights, and windows from a compressed `ex*.py` source.
- Constructs a cutting line that advances northward from the original south boundary.
- Retains the polygon on the north side of the line.
- Extrudes each retained polygon into a three-dimensional thermal zone.
- Rebuilds floors, roofs, exterior walls, and adjacent walls.
- Preserves each projected south-window X coordinate and Z elevation.
- Retains the template's non-geometric objects.

## Example

```powershell
python .\01_Postprocessing_Toolkit\Oblique_Cutting\cut_idf.py `
  --source "C:\path\to\ex1-01-06.py" `
  --template "C:\path\to\Empty_Zone_Template_01_06.idf" `
  --angle 60 `
  --output ".\task4_cut60.idf" `
  --report ".\task4_cut60_report.json"
```

## Line Modes

The default `normalized` mode maps the angle to a northward cut depth:

```text
east_end_cut_depth = building_depth * sin(angle)
```

This mode normally retains the original number of zones. Alternatives are:

```powershell
--cut-ratio 0.5
--cut-depth 3.0
--line-mode absolute --angle 30
```

`absolute` uses the physical `tan(angle)` slope and can remove entire zones from a long, shallow building. Add `--allow-removed-zones` only when that outcome is intended.

## Window Projection

For every south-wall window vertex:

- X remains unchanged.
- Y becomes the cutting-line Y value at that X coordinate.
- Z remains unchanged.

The perpendicular window offset from the west or east side wall is therefore retained. Windows that no longer lie on an exterior wall are omitted and reported.

## Validation

The report records input and output zone counts, surface and window counts, projected-window count, maximum X displacement, zone area ratios, sloped-wall count, and footprint vertex counts.
