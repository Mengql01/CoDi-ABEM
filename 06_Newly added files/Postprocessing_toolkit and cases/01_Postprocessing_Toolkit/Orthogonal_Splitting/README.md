# Orthogonal Zone Splitting

`split_idf.py` divides selected thermal zones at user-specified X or Y distances and rebuilds the IDF geometry.

## Capabilities

- A target zone is always required.
- X/EW cuts are measured from the zone's west wall.
- Y/NS cuts are measured from the zone's south wall.
- Multiple cut distances may be provided in one operation.
- X and Y cuts may be combined to create a grid.
- `--sync-vertical` applies the same split to vertically aligned floors.
- Exterior windows are reassigned to child zones; a window crossed by a cut is divided into valid window fragments.
- New partitions are written as paired adjacent walls.

## Examples

Single cut:

```powershell
python .\01_Postprocessing_Toolkit\Orthogonal_Splitting\split_idf.py `
  --source "C:\path\to\ex1-01-06.py" `
  --template "C:\path\to\Empty_Zone_Template_01_06.idf" `
  --split zone03:x:3 `
  --output ".\task4_zone03_x3.idf" `
  --report ".\task4_zone03_x3_report.json"
```

Multiple cuts and synchronized floors:

```powershell
--split zone03:x:3,6 --sync-vertical
```

Combined X/Y grid:

```powershell
--split zone03:x:3,6 --split zone03:y:2.5
```

## Split Syntax

```text
zone:axis:distances
```

`axis` accepts `x`/`ew` or `y`/`ns`. Multiple distances are comma-separated.

## Validation

The program checks unique zone and surface names, valid child dimensions, parent-wall references, new interior-wall counts, and window fragments. The JSON report records every split and the resulting object counts.
