# Unified IDF Geometry Toolkit

This directory provides a single command-line entry point:

- `idf_toolkit.py`
- `idf_toolkit.bat`

The wrapper exposes the original geometry tools and the case-specific `restore13` workflow.

## Usage

```powershell
.\idf_toolkit.bat <command> <arguments>
```

Run an underlying tool with:

```powershell
.\idf_toolkit.bat run <tool> <original-tool-arguments>
```

Available tool aliases:

| Alias | Tool |
|---|---|
| `complex` | Complex component assembly |
| `angle-cut` | Oblique footprint cutting |
| `split` | Orthogonal zone splitting |
| `merge` | Rectangular zone merging |

Example:

```powershell
.\idf_toolkit.bat run split `
  --source "C:\path\to\ex1-01-06.py" `
  --template "C:\path\to\Empty_Zone_Template_01_06.idf" `
  --split zone03:x:3 `
  --sync-vertical `
  --output ".\task4_split.idf"
```

## Case-Specific Restoration

```powershell
.\idf_toolkit.bat restore13 `
  --input ".\rectangular_18zone.idf" `
  --reference ".\reference_13zone.idf" `
  --output ".\restored_13zone.idf" `
  --report ".\restored_13zone_report.json" `
  --operations ".\restored_13zone_operations.json" `
  --svg ".\restored_13zone_plan.svg"
```

`restore13` restores an 18-zone rectangular intermediate model to the verified 13-zone complex topology. It preserves the reference surface vertex order and window parent relationships.

The reproducible case-specific operation records are stored under `04_Manual_Restoration_Case_Studies`, rather than in this tool directory.

## Important Topology Rule

The historical restoration workflow and the final GUI do not automatically merge coplanar zero-gap wall pieces. Interior surfaces must remain one-to-one with equal-size adjacent surfaces for reliable Trn3D import.
