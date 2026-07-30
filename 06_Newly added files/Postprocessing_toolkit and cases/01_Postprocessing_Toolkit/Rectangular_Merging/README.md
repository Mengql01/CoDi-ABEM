# Rectangular Zone Merging

`merge_idf.py` merges user-selected adjacent rectangular thermal zones and rebuilds a valid six-surface rectangular zone.

## Capabilities

- Merge one pair or several independent pairs in a single run.
- Detect the shared wall automatically or validate a specified axis and distance.
- Remove the shared interior wall.
- Rebuild the four side walls, floor, and roof as exactly six surfaces.
- Reassign every window to the correct rebuilt parent wall.
- Keep separated windows distinct; join immediately contiguous windows on the same parent wall.

## Geometric Constraint

Every merge result must remain a clean rectangular prism. The union bounding-box volume must equal the sum of the input zone volumes, and each final face must have one boundary object.

For a stacked model, corresponding zones on adjacent floors may also need to be merged. Otherwise one rebuilt ceiling could face more than one unmerged zone, which cannot be represented as a single IDF surface with one boundary object.

## Example

```powershell
python .\01_Postprocessing_Toolkit\Rectangular_Merging\merge_idf.py `
  --source "C:\path\to\ex1-01-06.py" `
  --template "C:\path\to\Empty_Zone_Template_01_06.idf" `
  --merge zone03+zone04:auto `
  --merge zone08+zone09:auto `
  --output ".\task4_merge_03_04_08_09.idf" `
  --report ".\task4_merge_03_04_08_09_report.json"
```

## Merge Syntax

```text
zoneA+zoneB[:axis[:distance]]
```

Examples:

```powershell
--merge zone03+zone04:auto
--merge zone03+zone04:x:8.1
--merge 3+4:x:8.1
```

`x`, `y`, and `z` specify the shared boundary's distance from the merged zone's west, south, or bottom face. `auto` detects a full-face adjacency.

## Validation

The program verifies full-face adjacency, rectangular-prism union geometry, exactly six surfaces per final zone, valid window parent references, and unique object names. The JSON report records merge groups and before/after object counts.
