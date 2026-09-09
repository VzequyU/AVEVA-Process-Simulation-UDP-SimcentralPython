# AVEVA Process Simulation — Python Experiment Starter

Reusable examples for connecting **AVEVA Process Simulation (APS)** to Python with a **custom EETK DLL over UDP** and the **`simcentralconnect` scripting interface**.

Use the same connection layer for an individual experiment, a sequential parameter sweep, or an Opyrability model evaluation. Process variables are configured in JSON rather than hard-coded into the engine.

**Author:** Ezequiel José Valencia Urbina — University of Brasília (UnB).

## How the connection works

| Connection | Responsibility |
|---|---|
| Python → UDP → custom DLL → APS model | Apply commanded process inputs through the DLL's model bindings. |
| APS model → custom DLL → UDP → Python | Return measurements and simulation timestamps. |
| Python → `simcentralconnect` → APS | Open the simulation, stop the solver, restore a snapshot and execute dynamics. |

The **custom process DLL runs inside APS**. Python does not load that DLL directly. `simcentralconnect` connects to the installed APS environment through the official scripting infrastructure. UDP does not start or pause APS in this design.

The DLL development project is available separately at [AVEVA-Process-Simulation-UDP](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP). Configure a compatible DLL and process model first. This repository does not contain the APS installer, vendor SDK assemblies, a compiled process DLL or the process model.

## What can be reused?

The engine supports any configured number of numeric inputs and outputs **when the custom DLL implements the selected protocol**:

- Flat UTF-8 JSON commands, or a plain numeric command for a single-input DLL.
- Flat UTF-8 JSON telemetry containing named numeric measurements and a simulation clock in seconds.
- A prepared Dynamics snapshot and the demonstrated APS lifecycle methods.

Changing a JSON key in Python does not create a variable or modify the DLL. New process variables must also be bound and serialized correctly in the custom DLL. Units in configuration document the contract; the engine does not perform unit conversion. See [adapting another simulation](docs/adapt_another_simulation.md).

## Files

| File | Purpose |
|---|---|
| `aveva_engine.py` | Configurable connection, snapshot reset, concurrent UDP reception and result logging. |
| `run_experiment.py` | Run one configured input vector. |
| `test_aveva_engine.py` | Equivalent manual integration entry point for checking the connection. |
| `automated_experiments.py` | Sequential constant-input grid experiments. |
| `opyrability_oi.py` | Fixed-horizon input/output map and raw OI evaluation. |
| `config/four_tanks.json` | Concrete four-tank connection example. |
| `config/generic_valve.template.json` | Starting template for another process; edit before use. |
| `config/grid_four_tanks.json` | Nine-trial grid example. |
| `config/operability_four_tanks.json` | Illustrative two-level DOS and resolution. |
| `tests/test_engine_offline.py` | Offline tests with real UDP sockets and fake APS services. |
| `docs/` | Connection instructions, protocol details and English LaTeX guide. |

## 1. Prepare your environment

Use the Windows Python environment in which `import simcentralconnect` and `simcentralconnect.connect().Result` already work. Obtain the connector and APS/EETK dependencies through your installed product's supported setup. Do not copy vendor DLLs into this repository or assume an arbitrary PyPI package is the correct connector.

The engine, single experiment and sweep use Python's standard library plus the configured AVEVA connector. The Opyrability example additionally needs NumPy and the exact Opyrability revision required by your project. This starter does not claim a verified dependency lock for that revision.

Open your process model, deploy its custom DLL, check variable specifications, and prepare a named snapshot in Dynamics mode. Stop other programs using UDP port 5005.

## 2. Configure the model

Edit `config/four_tanks.json` or make a copy for your own process. Set:

- `simulation` and `snapshot`: exact APS names.
- `udp`: bind address, peer address, ports and command format.
- `inputs`: logical name, DLL wire key, units and allowed bounds.
- `outputs`: logical name, DLL wire key and units.
- `run.argument`: argument passed to `RunDynamics` in seconds.
- `run.expected_final_time`: independently expected final telemetry clock value.
- `run.time_key` and `run.time_tolerance`: clock field and endpoint tolerance.

For example, logical input `feed_1` maps to JSON key `q1`; logical output `level_1` maps to telemetry key `h1`. `aps_path` is documentation for the DLL binding, not a call to `IVariableManager`.

The supplied four-tank defaults use `Sim 3`, snapshot `start dym` and a 20-second run from the tested base case. Verify whether your installed `RunDynamics` interprets its argument as a duration or target time before changing starting clocks. The engine does not guess this from `.NET` type names.

## 3. Check one experiment

From the repository root:

```powershell
python -u test_aveva_engine.py --config config/four_tanks.json
```

Or supply a different input vector using the configured logical names:

```powershell
python -u run_experiment.py --config config/four_tanks.json --inputs '{"feed_1": 0.08, "feed_2": 0.05}'
```

If PowerShell's native argument handling changes the JSON quoting, edit `example_inputs` in the configuration and omit `--inputs`. Use the full path to your working Python interpreter if needed.

The engine stops and restores the base snapshot, checks Dynamics mode, starts the receiver, sends the command, runs APS and collects telemetry. It attempts to stop and restore the base case after each run, including failures. It does not close the user's APS simulation.

## 4. Run automated experiments

```powershell
python -u automated_experiments.py --config config/four_tanks.json --grid config/grid_four_tanks.json
```

Each trial independently restores the same base snapshot. Successful trial rows are saved incrementally to a uniquely named CSV. A failed trial stops the sweep and retains its result record and raw telemetry.

## 5. Evaluate a fixed-horizon operability region

First verify the installed package using [the Opyrability notes](docs/operability.md), then set the actual output requirements in the study file:

```powershell
python -u opyrability_oi.py --config config/four_tanks.json --study config/operability_four_tanks.json
```

The supplied level DOS is illustrative. The script prints the installed signatures and package version, and reports the raw OI return without assuming percentage scaling.

This is a **constant-input, fixed-horizon map**. A full dynamic funnel requires propagation from retained complete states under changing input sequences. That algorithm is explained in the guide but is not implemented by these examples.

## Results and validation

Every run creates `results/<run-id>/telemetry.jsonl` and `result.json`. Raw telemetry preserves receive order and malformed messages; the result includes configuration, input values, output observations, timing and cleanup outcomes.

`success: true` means APS returned success, usable telemetry reached the expected clock within tolerance, and cleanup succeeded. It does **not** prove command acknowledgement or accepted-step sampling. `command_applied_verified` remains false because the existing DLL contract has no acknowledgement. Intermediate solver iterates can be present in the stream. Verify the DLL's sampling semantics before drawing quantitative reachability conclusions.

A snapshot may not reset private DLL memory or queued commands. The engine drains immediately queued telemetry and sends a complete input vector, but it cannot guarantee a protocol-level reset without DLL support. See [protocol details](docs/protocol.md).

## Testing and status

```powershell
python -m unittest discover -s tests -v
```

Five offline tests passed: command mapping and bounds rejection, scalar commands, concurrent UDP reception with invalid-packet handling, restoration after run failure, and rejection of an incorrect endpoint time. These tests exercise real localhost UDP with fake simulator services. **This refactored version has not been executed against APS or the required Opyrability 2.0 installation here.**

No module connects to APS merely when imported. Keep your own multiprocessing entry points under `if __name__ == "__main__":` on Windows. Use one engine/port pair sequentially; these examples do not coordinate concurrent access to a shared simulation.

## License

No code license has been selected in this starter. The author should choose one for their own contributions. AVEVA and third-party components remain subject to their own terms and are not redistributed here.
