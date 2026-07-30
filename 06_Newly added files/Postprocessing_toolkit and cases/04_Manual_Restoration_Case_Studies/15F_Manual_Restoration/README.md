# 15th-Floor Manual Restoration

This case restores an 18-zone rectangular intermediate IDF to a 13-zone complex model.

## Files

- `input/manual_restore_input.idf`: rectangular input.
- `reference/reference_13zone.idf`: original complex-zone reference.
- `output/manual_restore_input_processed.idf`: final GUI-generated output retained for the case study.
- `records/manual_restore_operations.json`: grouped, machine-readable restoration recipe.
- `records/manual_restore_validation_report.json`: object counts and SHA-256 checksums for the published input, reference, and output.
- `documentation/GUI_User_Guide.md`: operation and validation instructions.

The distributed implementation preserves adjacent-wall segmentation. It does not use the deprecated zero-gap surface-coalescing strategy.

The grouped operation recipe is the authoritative reproduction record. Historical GUI session snapshots with superseded parameters are intentionally excluded.
