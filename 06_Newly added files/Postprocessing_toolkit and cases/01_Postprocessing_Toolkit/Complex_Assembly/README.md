# Complex Building Assembly

`combine_idf.py` combines compact rectangular five-zone or ten-zone models into T- or H-shaped buildings before writing the reconstructed geometry into an IDF template.

## Method

1. Read the compressed `zones` list from an `ex*.py` source file.
2. Treat each source model as a component that may be rotated to an east-west (`ew`) or north-south (`ns`) orientation and translated.
3. Detect floors and zones per floor automatically.
4. Merge user-selected component zones. A merged thermal zone may have an L-, T-, or Z-shaped footprint.
5. Rebuild `Zone`, `BuildingSurface:Detailed`, and `FenestrationSurface:Detailed` objects.
6. Preserve all non-geometric template content that appears before the first `Zone` object.

## Automatic Connection Rules

### T shape

The default layout uses one north-south main component and one east-west branch. On each floor, the middle zone of the main component is merged with the first zone of the branch. A two-floor, five-zone-per-floor source therefore changes from 20 input zones to 18 final zones.

### H shape

The default layout uses two north-south side components and one east-west connector. The connector endpoints are merged with the middle zone of each side component on every floor. A two-floor source changes from 30 input zones to 26 final zones.

## Examples

From the repository root:

```powershell
python .\01_Postprocessing_Toolkit\Complex_Assembly\combine_idf.py `
  --shape T `
  --source "C:\path\to\ex1-01-06.py" `
  --template "C:\path\to\Empty_Zone_Template_01_06.idf" `
  --output ".\task4_T.idf" `
  --report ".\task4_T_report.json"
```

Generate an H-shaped case by changing `--shape T` to `--shape H`.

## Manual Merge Specification

Repeat `--merge role:zone=role:zone` to override the automatic connection rules:

```powershell
--merge main:3=branch:1 --merge main:8=branch:6
```

H-shaped example:

```powershell
--merge left:3=connector:1 `
--merge connector:5=right:3 `
--merge left:8=connector:6 `
--merge connector:10=right:8
```

## Important Options

| Option | Description |
|---|---|
| `--shape T\|H` | Select the assembled footprint. |
| `--source` | Default compressed source used by every component. |
| `--main-source`, `--branch-source` | Use different sources for a T-shaped model. |
| `--left-source`, `--connector-source`, `--right-source` | Use different sources for an H-shaped model. |
| `--main-orientation`, `--branch-orientation` | T-component orientation (`ns` or `ew`). |
| `--side-orientation`, `--connector-orientation` | H-component orientation. |
| `--attach-side` | Attach the T branch to the east, west, north, or south side. |
| `--merge` | Define an explicit pair of zones to merge. |
| `--report` | Write a JSON validation report. |

## Validation

The program checks component contact, positive-volume overlap, connected merged footprints, duplicate object names, and window parent surfaces. Windows on removed contact walls are omitted and counted in `dropped_windows`.
