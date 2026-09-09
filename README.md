# AVEVA Process Simulation: UDP + Simcentral Python

Automate dynamic experiments in AVEVA Process Simulation (APS) using a custom EETK DLL for UDP process-data exchange and `simcentralconnect` for simulation lifecycle control.

**Author:** Ezequiel José Valencia Urbina — University of Brasília (UnB).

## Architecture

| Component | Role |
|---|---|
| APS | Solve the physical process model and its dynamics. |
| Custom EETK DLL + UDP | Receive manipulated inputs and transmit process measurements. |
| `simcentralconnect` | Open the simulation, run dynamics, stop execution and restore a snapshot. |
| Python | Coordinate experiments, receive telemetry and save results. |

The custom bridge project is maintained in [AVEVA-Process-Simulation-UDP](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP). Configure a compatible four-tank bridge before running this example. This repository does not bundle the AVEVA SDK, proprietary assemblies or an APS model.

## Current status

- A single-run APS/UDP experiment has been demonstrated in the author's Windows environment.
- A small nine-run, constant-input endpoint dataset is included.
- The technical guide includes an Opyrability integration chapter.
- A complete dynamic-funnel implementation and compatibility with the required Opyrability 2.0 revision have **not yet been validated**.

The script in this starter was syntax-checked here; APS execution must be verified on the configured Windows machine. It uses the three-argument `RunDynamics(name, time, unit)` call shown in the successful experiment. Spanish console messages from the original test are retained.

## Repository contents

| Path | Contents |
|---|---|
| `examples/aps_udp_dynamic_test.py` | Single-run experiment with a separate UDP receiver process. |
| `docs/APS_UDP_Simcentral_Guide_EN.tex` | English guide, including the Opyrability chapter. |
| `docs/setup.md` | Configuration and execution instructions. |
| `docs/protocol.md` | Existing four-tank UDP message contract. |
| `docs/roadmap.md` | Next steps and pending code review. |
| `data/sample/` | Small endpoint dataset and its interpretation. |
| `src/README.md` | Planned home for the reviewed reusable modules. |
| `tests/README.md` | Planned home for APS integration tests. |

## Quick start

1. Use a Windows machine with APS and an already working `simcentralconnect` Python environment.
2. Load the process model and compatible custom DLL. Prepare a Dynamics snapshot.
3. Close other Python programs receiving on UDP port 5005.
4. Edit the configuration constants at the top of `examples/aps_udp_dynamic_test.py`.
5. From the repository root, run:

```powershell
python -u examples/aps_udp_dynamic_test.py
```

Use the full path to your working Python executable if `python` resolves to a different environment. The communication example uses Python's standard library plus the locally configured AVEVA connector; it does not require Opyrability, NumPy or Matplotlib.

Default example settings are simulation `Sim 3`, snapshot `start dym`, inputs `q1=0.08` and `q2=0.05` kg/s, and run argument `20.0` seconds. These defaults must match your own model.

The script changes simulation inputs through UDP, executes dynamics, attempts to stop the solver, and attempts to restore the snapshot. Inspect both the run result and cleanup messages. Do not infer success from `Restauracion final: True` alone.

See [setup instructions](docs/setup.md) and [protocol details](docs/protocol.md).

## Results and limitations

Raw telemetry is written under `examples/resultados_udp/`, which is excluded from version control. The supplied successful experiment received 754 valid JSON packets through simulation time 20 seconds, with a wall-clock runtime of approximately 1.59 seconds. This is an observed run, not a timing or losslessness guarantee.

UDP transmission does not acknowledge that APS applied an input. The existing telemetry does not contain command acknowledgements or packet sequence numbers. Solver telemetry may contain repeated/intermediate observations; verify the endpoint before treating it as a simulation result. `RunDynamics` time semantics from nonzero initial times also require local validation.

## Documentation

Upload `docs/APS_UDP_Simcentral_Guide_EN.tex` to Overleaf as the main file, or compile it locally with a suitable LaTeX installation. Export the current PDF to `docs/APS_UDP_Simcentral_Guide_EN.pdf` if you want a browser-readable copy in GitHub. The older integration PDF is not included because it predates the appended Opyrability chapter.

The guide's runner interfaces and funnel pseudocode are implementation contracts, not executable functions supplied by this repository.

## Licensing

No license has been selected for this starter. The author should choose a license for their own code before inviting reuse. AVEVA software and third-party SDK components retain their own licensing terms and are not distributed here.
