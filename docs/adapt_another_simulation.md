# Adapt the connection to another simulation

## A. Define the process interface

Decide which variables Python commands, which variables Python observes, their units and limits, and how to export the simulation clock. Keep model state variables separate from the selected plotted outputs.

For a valve example, the proposed contract can be:

```json
{"opening": 0.5}
```

with telemetry:

```json
{"sim_time": 20.0, "flow": 1.2}
```

Those are example fields, not built-in APS variable names. The valve DLL must implement them. If your existing valve DLL accepts a plain number, set `command_format` to `scalar`. If it does not export a clock, extend its telemetry before using this fixed-horizon runner.

## B. Prepare the DLL in APS

1. Start from the working EETK project or the official example compatible with your APS installation.
2. Bind each configured signal to its actual process variable and units.
3. Use supported external equations to impose commanded inputs and keep the model's specifications consistent.
4. Implement the selected command parser and JSON telemetry format.
5. Avoid blocking network waits inside equation evaluation; handle command synchronization and DLL disposal explicitly.
6. Build/deploy the DLL with the framework, architecture and references required by your APS version.
7. Confirm input response and telemetry in the actual simulation, then prepare a Dynamics snapshot.

The engine does not generate, compile or deploy this model-specific DLL. See the supplied LaTeX guide for the DLL workflow. No universal EETK class signature is fabricated here.

## C. Configure Python

Copy `config/generic_valve.template.json` and replace the simulation/snapshot names, addresses, port numbers and variable mappings. The `aps_path` fields document your DLL bindings; this engine never sets them using the variable API.

Choose a run argument and expected final clock independently based on your installed APS behavior. All times used here are seconds. Input and output units are descriptive: perform any necessary conversion in a deliberate, documented place.

Then run:

```powershell
python -u run_experiment.py --config config/my_process.json
```

## D. Reuse the engine in your own code

```python
from aveva_engine import AVEVAEngine, load_config

def main():
    engine = AVEVAEngine(load_config("config/my_process.json")).connect()
    result = engine.run({"valve_opening": 0.5})
    print(result["outputs"]["outlet_flow"])

if __name__ == "__main__":
    main()
```

`run()` is an independent experiment and automatically returns to the base snapshot. It is not a continuation-step interface. To implement closed-loop control or dynamic branching, add and validate a stateful lifecycle interface that does not reset at every control interval.

## Publication scope

Upload the source, configurations, documentation and offline tests. Keep generated results, Python caches and local vendor assemblies out of the repository. If you add a distributable process model or your own DLL source, document its version and requirements. Do not describe a screenshot of a file list as included runnable code.
