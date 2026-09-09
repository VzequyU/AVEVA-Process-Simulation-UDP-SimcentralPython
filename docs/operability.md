# Using the Opyrability example

The supplied `opyrability_oi.py` adapts the original user's `multimodel_rep` and `OI_eval` call pattern. It imports analysis dependencies only when run, creates one APS engine, and evaluates input vectors sequentially from the same snapshot.

Before running APS, inspect the required installation:

```python
import inspect
import opyrability
from importlib import metadata
print(opyrability.__file__)
try:
    print(metadata.version("opyrability"))
except metadata.PackageNotFoundError:
    print("Record the source checkout commit")
print(inspect.signature(opyrability.multimodel_rep))
print(inspect.signature(opyrability.OI_eval))
```

Confirm that this is the Opyrability 2.0 revision required by your project and consult its function documentation. The starter checks optional keyword availability but cannot establish semantic compatibility with an untested revision.

AIS bounds come from the input configuration, in its input order. The study file supplies input-grid resolution, two selected output names and corresponding DOS bounds. The engine can use any number of outputs; this particular region example selects two. Do not reuse mass-flow DOS limits for level outputs.

Cache entries use exact input tuples and live only for one fixed configuration and horizon. Every uncached evaluation resets APS, applies a constant input, executes the run and saves its own result record. The region and OI therefore describe a sampled, fixed-horizon, constant-input map. The current UDP endpoint qualification remains provisional.

The returned OI is saved without assuming a fraction/percentage convention. A numeric OI is not a control-performance guarantee. Check region dimensionality, grid sensitivity, physical admissibility and DLL endpoint sampling before reporting a scientific result. This example does not enforce continuous path constraints.

For a dynamic funnel, retain or reconstruct the entire branch state between intervals; repeatedly restoring the base snapshot does not propagate the reachable set. See the final chapter of `APS_UDP_Simcentral_Guide_EN.tex` for the mathematical distinction.
