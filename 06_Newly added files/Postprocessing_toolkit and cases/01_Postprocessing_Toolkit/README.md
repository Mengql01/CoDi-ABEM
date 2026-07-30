# Post-Processing Toolkit

The toolkit is organized by operation type. Each tool reads either a compact Python zone description or an IDF/reference pair and writes a reconstructed IDF geometry block.

| Directory | Primary entry point | Purpose |
|---|---|---|
| `Complex_Assembly` | `combine_idf.py` | Assemble T-, H-, and related component layouts. |
| `Oblique_Cutting` | `cut_idf.py` | Apply a sloped footprint cut and project windows. |
| `Orthogonal_Splitting` | `split_idf.py` | Split selected zones along X or Y. |
| `Rectangular_Merging` | `merge_idf.py` | Merge adjacent rectangular zones. |
| `Archetype_Case_Generator` | `archetype_idf.py` | Generate the first seven representative complex cases. |
| `Roof_Lifting` | `roof_lift_idf.py` | Generate roof-lift geometries. |
| `Unified_Toolkit` | `idf_toolkit.bat` | Provide one command-line wrapper and restoration workflow. |

This directory contains only executable tool source code and the usage guides required to run it. Case inputs, generated outputs, validation artifacts, and case-specific conversion materials are kept out of the toolkit directory.

All runtime tools use the Python standard library. Users provide their own compressed `ex*.py` source, IDF template, or IDF/reference pair through command-line arguments.
