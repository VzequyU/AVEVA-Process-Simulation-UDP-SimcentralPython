# Implementation roadmap

## Included now

The single-run communication test, current LaTeX guide, and a small endpoint dataset.

## Review before importing the remaining local files

| Local file | Proposed destination after review |
|---|---|
| `aveva_engine.py` | `src/aveva_engine.py` |
| `opyrability_aps.py` | `src/opyrability_aps.py` |
| `opyrability_oi.py` | `src/opyrability_oi.py` |
| `opyrability_region.py` | `src/opyrability_region.py` |
| `opyrability_time_sweep.py` | `src/opyrability_time_sweep.py` initially, preserving existing sibling imports |
| `test_aveva_engine.py` | `tests/test_aveva_engine.py` once imports and execution are configured |
| `dynamic_operability_4tanks.py` | `examples/fixed_horizon_map_4tanks.py` after the fixes below |

The engine and Opyrability module contents were not supplied with the folder screenshot. Their imports and runtime behavior must be reviewed before moving them into this structure. Merely moving modules does not create an installable Python package.

## Known sweep-script work

The earlier `dynamic_operability_4tanks.py` version is not included as a release example. It accumulates all packets, passes them through a multiprocessing queue, joins the worker before draining that queue, imports the APS connector at module scope, and needs stronger failure cleanup and endpoint verification. Refactor it to stream telemetry to disk, return small summaries, initialize APS in the parent only, and restore the base case on failed runs as well as successful ones.

Rename the revised example to reflect its constant-input, fixed-horizon scope. It does not compute the full dynamic funnel.

## Next analysis steps

1. Verify the required Opyrability revision and its function signatures.
2. Validate the fixed-horizon APS runner and define the level DOS.
3. Check repeatability and grid sensitivity of output coverage.
4. Implement full-state restore or deterministic replay for input sequences.
5. Compare a short exhaustive funnel with any boundary-based reduction.
