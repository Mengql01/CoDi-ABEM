# IDF Geometry GUI User Guide

Double-click `Launch_IDF_Geometry_GUI.bat` to start the mouse-driven interface.

## Runtime Directories

- `input`: place exactly one input IDF here.
- `output`: generated IDF and SVG files are written here.
- `records`: validation reports, operation records, and GUI session records are written here.

At startup, the application scans `input`, identifies thermal zones, and draws a plan view.

## General Workflow

1. Click a zone in the plan view or select it in the **Available zones** list.
2. Choose `split`, `merge`, `trim_merge`, or `map`.
3. Enter the required parameters and choose **Add to queue**.
4. Repeat for every desired operation.
5. Choose **Validate and Export**.

Queue controls:

- **Delete selected** removes one or more selected operations.
- `Delete` performs the same action.
- **Undo last** removes the most recent operation.
- `Ctrl+Z` deletes selected queue items first, or otherwise undoes the latest item.
- `Ctrl+Enter` validates and exports.

## Operation Types

### Split

Select one zone, choose an axis, and enter a global cut coordinate.

- `x`: vertical plan cut.
- `y`: horizontal plan cut.

The GUI displays the selected zone's valid coordinate range and rejects a cut outside that range.

### Merge

Select two or more zones and enter the output zone name. If that name already exists, the interface adds a numeric suffix for display without overwriting the existing zone.

### Trim merge

Select at least two zones and choose one parameter mode:

- `line`: enter a complete target boundary as `(x0,y0)-(x1,y1)`.
- `points`: enter two local trim points as `(x0,y0),(x1,y1)`.

The parameter field begins with an empty template. Case-specific coordinates are never inserted or reused automatically.

In `line` mode, the line is the complete target south boundary. Geometry below the line is removed, and missing geometry above the line is extended down to the line. This prevents steps at intermediate rectangular-zone boundaries.

### Map

Select one unchanged source zone and enter its final output name.

## Verified 18-to-13 Restoration Recipe

The following case-specific recipe is included as a reproducibility example. The GUI remains a general tool and does not require this recipe for other valid exports.

### Batch 1: four splits

```text
split zone07 x=16.6
split zone15 x=16.6
split zone11 x=22.05
split zone12 x=17.15
```

### Batch 2: five merges

```text
merge zone01+zone07_west -> zone01
merge zone07_east+zone16 -> zone06
merge zone02+zone03 -> zone02
merge zone10+zone11_east -> zone11
merge zone13+zone14+zone12_west -> zone13
```

### Batch 3: three trimmed merges

Use one complete south line for the first two operations:

```text
(0,0)-(34.2,8.054235169875)
```

Then add:

```text
trim_merge zone06+zone15_west -> zone05 line=(0,0)-(34.2,8.054235169875)
trim_merge zone15_east+zone18 -> zone08 line=(0,0)-(34.2,8.054235169875)
trim_merge zone11_west+zone12_east -> zone12 points=(22.05,25.567114767738),(25.4,25.467114767738)
```

### Batch 4: five mappings

```text
map zone04 -> zone03
map zone05 -> zone04
map zone17 -> zone07
map zone08 -> zone09
map zone09 -> zone10
```

## Validation and Export

Before export, the application checks:

- the queue is not empty;
- every referenced zone exists at that operation step;
- split coordinates lie inside the selected zone;
- merge and trim-merge operations select enough zones;
- map operations select exactly one zone;
- output-name collisions can be resolved safely;
- duplicate operations and other risks.

An incomplete match to the built-in restoration recipe is shown only as a warning. It does not prevent a valid general-purpose export.

The final implementation preserves one-to-one adjacent-wall segmentation and does not merge coplanar zero-gap surfaces.

## Output Names

For an input named `example.idf`, the GUI writes files such as:

```text
output/example_processed.idf
output/example_processed.svg
records/example_report.json
records/example_operations.json
records/example_gui_session_TIMESTAMP.json
```
