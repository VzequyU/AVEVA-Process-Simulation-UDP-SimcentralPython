<p align="center">
  <img src="https://img.shields.io/badge/AVEVA-Process%20Simulation-purple?style=for-the-badge&logo=data:image/png;base64," alt="AVEVA"/>
  <img src="https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/SimCentral-Connect%20API-teal?style=for-the-badge" alt="SimCentral"/>
  <img src="https://img.shields.io/badge/Protocol-TCP%20v2%20%7C%20UDP%20v1-orange?style=for-the-badge" alt="TCP v2 and UDP v1"/>
  <img src="https://img.shields.io/badge/Opyrability-OI%20Evaluation-red?style=for-the-badge" alt="Opyrability"/>
</p>

<h1 align="center">⚙️ AVEVA Process Simulation<br>Automated Experiment Engine</h1>

<p align="center">
  <strong>Automate simulation experiments without touching the GUI</strong><br>
  <em>Single runs, parameter sweeps, and operability analysis — all from Python scripts.</em>
</p>

<p align="center">
  <a href="#-quick-start">🚀 Quick Start</a> •
  <a href="#-how-the-connection-works">🔗 Connection</a> •
  <a href="#-automated-experiments">🔄 Sweeps</a> •
  <a href="#-operability-analysis">📊 Opyrability</a> •
  <a href="docs/">📖 Docs</a>
</p>

---

## 🎯 What Is This?

This repository provides a **reusable Python engine** for running automated experiments on [AVEVA Process Simulation (APS)](https://www.aveva.com/en/products/process-simulation/) — without manual interaction with the simulator GUI.

It combines two communication channels:

- **`simcentralconnect`** — the official scripting API that controls the simulation lifecycle (open, stop, snapshot, run dynamics)
- **Custom EETK DLL** — data exchange with the process model, over one of two transports:
  - **`tcp_v2` (recommended)** — bridge version 2: one sample per *accepted* integration step, commands
    acknowledged with the simulation time at which they took effect, rejected steps reported (`rewind`)
  - **`udp` (v1)** — original bridge: one datagram per residual evaluation, no acknowledgement

```
┌────────────────────┐                              ┌────────────────────────┐
│     Python Side    │     simcentralconnect API     │       APS Side         │
│                    │─────────────────────────────►│                        │
│  aveva_engine.py   │  Open, Stop, Snapshot, Run   │  Simulation Manager    │
│  ─────────────────│                              │  Snapshot Manager      │
│  run_experiment.py │         UDP Commands          │  ──────────────────── │
│  automated_exp.py  │─────────────────────────────►│  Custom EETK DLL      │
│  opyrability_oi.py │◄─────────────────────────────│  (EquationSet.cs)     │
│                    │        UDP Telemetry          │  ──────────────────── │
│  config/*.json     │                              │  EO Dynamics Solver    │
│  results/          │                              │  Process Model         │
└────────────────────┘                              └────────────────────────┘
```

> **🔗 Prerequisite:** The DLL development project is available at [AVEVA-Process-Simulation-UDP](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP). Configure a compatible DLL and process model first.

### Key Features

- ✅ **JSON-configured** — change process, variables, and bounds without editing code
- ✅ **Snapshot-based reset** — every experiment starts from the exact same initial condition
- ✅ **Two transports** — TCP bridge v2 (acknowledged commands, accepted-step samples) or UDP v1
- ✅ **Steady-state runs** — `run.settle` extends a run until every output stops changing (TCP v2)
- ✅ **Incremental logging** — raw telemetry (JSONL) + structured results (JSON) + sweep CSV
- ✅ **Grid sweeps** — sequential constant-input experiments over a parameter grid
- ✅ **Opyrability integration** — fixed-horizon OI evaluation via the `opyrability` package
- ✅ **Offline tests** — real UDP sockets with mock APS services for CI-safe validation

---

## 🔗 How the Connection Works

| Channel | Direction | Responsibility |
|---------|-----------|----------------|
| `simcentralconnect` → APS | Python → APS | Open simulation, stop solver, restore snapshot, execute dynamics |
| UDP → custom DLL → APS | Python → APS | Apply commanded process inputs through the DLL's model bindings |
| APS → custom DLL → UDP | APS → Python | Return measurements and simulation timestamps as JSON telemetry |

The **custom process DLL runs inside APS**. Python does not load the DLL directly. `simcentralconnect` connects to the installed APS environment through the official scripting infrastructure. UDP handles only data exchange — it does not start or pause the simulator.

### The Experiment Lifecycle

```
1. connect()     →  Open simulation via simcentralconnect
2. reset()       →  Stop solver + restore base snapshot
3. Verify mode   →  Confirm Dynamics mode is active
4. Start worker  →  Spawn UDP receiver (multiprocessing.spawn)
5. Drain queue   →  Discard stale datagrams from previous runs
6. Send command  →  UDP packet with input vector (JSON or scalar)
7. RunDynamics() →  Execute simulation for configured duration
8. Collect       →  Stream telemetry to disk, extract endpoint
9. Validate      →  Check final time against expected value ± tolerance
10. Cleanup      →  Stop solver + restore snapshot (always, even on failure)
```

---

## 📁 Project Structure

| File | Purpose |
|------|---------|
| `aveva_engine.py` | Core engine: configurable connection, snapshot reset, UDP or TCP v2 data path, steady-state runs, result logging |
| `bridge_v2.py` | TCP client for the version-2 DLL bridge (from the DLL repository) |
| `run_experiment.py` | Run a single configured input vector |
| `test_aveva_engine.py` | Manual integration entry point for checking the connection |
| `automated_experiments.py` | Sequential constant-input grid experiments |
| `opyrability_oi.py` | Fixed-horizon input/output map and raw OI evaluation |

| Configuration | Purpose |
|---------------|---------|
| `config/four_tanks.json` | Four-tank example, UDP v1 bridge |
| `config/four_tanks_tcp.json` | Four-tank example, TCP v2 bridge with steady-state runs |
| `config/generic_valve.template.json` | Starting template for another process (edit before use) |
| `config/grid_four_tanks.json` | Nine-trial grid example |
| `config/operability_four_tanks.json` | Illustrative two-level DOS and resolution |

| Support | Purpose |
|---------|---------|
| `tests/test_engine_offline.py` | Offline tests, UDP transport (real sockets, mock APS services) |
| `tests/test_engine_tcp_offline.py` | Offline tests, TCP v2 transport (fake DLL speaking the v2 protocol) |
| `docs/` | PDF guide: DLL and SimCentral coding |

---

## 🚀 Quick Start

### Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| AVEVA Process Simulation | 2023+ | Process simulator with EETK |
| Python | 3.8+ | With `simcentralconnect` working |
| Custom EETK DLL | Compatible | Deployed in your APS model ([build it here](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP)) |
| NumPy + [Opyrability](https://github.com/CODES-group/opyrability) | Optional | Only for `opyrability_oi.py` ([JOSS paper](https://doi.org/10.21105/joss.05966)) |

> ⚠️ Use the Windows Python environment where `import simcentralconnect` and `simcentralconnect.connect().Result` already work. Obtain the connector through your installed product's supported setup.

### Step 1 — Prepare the Simulation

Open your process model, deploy its custom DLL, verify variable specifications, and prepare a named snapshot in Dynamics mode. Stop other programs using the bridge ports (TCP 5006 for v2; UDP 5005/5006 for v1).

### Step 2 — Configure the Model

Edit `config/four_tanks.json` or copy it for your own process:

```jsonc
{
  "simulation": "Sim 3",           // Exact APS simulation name
  "snapshot": "start dym",         // Exact snapshot name in Dynamics

  "udp": {
    "bind_ip": "127.0.0.1",
    "peer_ip": "127.0.0.1",
    "receive_port": 5005,
    "send_port": 5006,
    "command_format": "json"       // "json" or "scalar" (single-input DLL)
  },

  "inputs": {
    "feed_1": { "key": "q1", "unit": "m³/s", "bounds": [0.0, 0.15] },
    "feed_2": { "key": "q2", "unit": "m³/s", "bounds": [0.0, 0.15] }
  },

  "outputs": {
    "level_1": { "key": "h1", "unit": "m" },
    "level_2": { "key": "h2", "unit": "m" }
  },

  "run": {
    "argument": 20,                // Passed to RunDynamics (seconds)
    "expected_final_time": 20,     // Expected telemetry clock endpoint
    "time_key": "t",
    "time_tolerance": 0.5,
    "unit": "s"
  }
}
```

For the **TCP v2 bridge**, replace the `udp` block by:

```jsonc
  "transport": "tcp_v2",
  "tcp": { "host": "127.0.0.1", "port": 5006, "timeout": 5.0, "apply": "step" },
  "run": {
    "argument": 2000, "unit": "s", "expected_final_time": 2000, "time_tolerance": 0.05, "time_key": "t",
    "settle": { "chunk": 500, "max_time": 20000, "window": 200, "tolerance": 1e-5 }
  }
```

`apply: "step"` applies the inputs at the next accepted step boundary (`"now"`: at the next evaluation).
`settle` is optional: after `argument` seconds the run is extended in `chunk` steps until every output
changes less than `tolerance` over the last `window` seconds, or `max_time` is reached (then the run
fails). See `config/four_tanks_tcp.json`.

> **Note:** Logical input `feed_1` maps to DLL wire key `q1`; logical output `level_1` maps to telemetry key `h1`. Changing a JSON key here does **not** create a variable in the DLL — new process variables must be bound and serialized in the C# code.

### Step 3 — Check One Experiment

```powershell
# Default input vector from config
python -u test_aveva_engine.py --config config/four_tanks.json

# Custom input vector
python -u run_experiment.py --config config/four_tanks.json --inputs '{"feed_1": 0.08, "feed_2": 0.05}'

# TCP v2 bridge, run until steady state
python -u run_experiment.py --config config/four_tanks_tcp.json
```

---

## 🔄 Automated Experiments

Run a parameter grid where each trial independently restores the base snapshot:

```powershell
python -u automated_experiments.py --config config/four_tanks.json --grid config/grid_four_tanks.json
```

**Grid configuration** (`config/grid_four_tanks.json`):
```json
{
  "feed_1": [0.03, 0.06, 0.09],
  "feed_2": [0.03, 0.06, 0.09]
}
```

This produces a 3×3 = 9 trial full-factorial sweep. Successful trial rows are saved incrementally to a uniquely named CSV. A failed trial stops the sweep and retains its result record and raw telemetry.

---

## 📊 Operability Analysis

The operability evaluation in this project uses [**Opyrability**](https://github.com/CODES-group/opyrability), a Python package for Process Operability analysis developed by **Victor Alves, San Dinh, John Kitchin, Vitor Gazzaneo, Juan C. Carrasco, and Fernando V. Lima** at the [CODES Group](https://fernandolima.faculty.wvu.edu/) (Carnegie Mellon University / West Virginia University).

> 📄 If you use the operability features of this project, please cite the Opyrability paper:
>
> Alves, V., Dinh, S., Kitchin, J. R., Gazzaneo, V., Carrasco, J. C., & Lima, F. V. (2024). **Opyrability: A Python package for process operability analysis.** *Journal of Open Source Software*, 9(94), 5966. [DOI: 10.21105/joss.05966](https://doi.org/10.21105/joss.05966)

### Running the OI Evaluation

```powershell
python -u opyrability_oi.py --config config/four_tanks.json --study config/operability_four_tanks.json
```

The script:
1. Builds a `model(u) → y` function backed by the APS engine
2. Caches evaluations to avoid re-simulating visited points
3. Calls `multimodel_rep` to construct the achievable output set (AOS)
4. Calls `OI_eval` against the desired output set (DOS) to compute the raw OI

> ⚠️ The operability index is defined on the **steady-state** map. With the UDP transport each point is
> the output at a fixed horizon, which is a steady state only if the horizon is long enough; use the
> TCP v2 transport with `run.settle` so that each point is checked. A dynamic operability funnel
> (changing input sequences) is not computed by this script.

Practical notes on `opyrability`:

- `resolution` must be a Python list, not a NumPy array;
- `OI_eval` takes the whole tuple returned by `multimodel_rep` and returns a **percentage**;
- for long, thin or strongly curved output sets, `OI_eval` slows down quickly as the grid is refined:
  start with a coarse resolution.

---

## 📋 Results and Validation

Every run creates a unique directory under `results/`:

```
results/
└── a1b2c3d4.../
    ├── telemetry.jsonl    # Raw UDP packets (receive order, including malformed)
    └── result.json        # Config, inputs, outputs, timing, cleanup status
```

With the TCP v2 transport, `telemetry.jsonl` holds one accepted-step sample per line.

**What `success: true` means:**

| Check | UDP v1 | TCP v2 |
|---|---|---|
| APS `RunDynamics` returned success | ✅ | ✅ |
| Telemetry reached the expected simulated time | ✅ (absolute clock) | ✅ (time elapsed after the acknowledged command) |
| Post-run cleanup (stop + snapshot restore) succeeded | ✅ | ✅ |
| Command acknowledged by the DLL | ❌ | ✅ (`command_applied_verified`) |
| Only accepted-step samples, no lost samples | ❌ | ✅ (samples invalidated by a rejected step are removed and reported) |
| Steady state verified | ❌ | ✅ with `run.settle` |

> With the UDP v1 bridge, intermediate solver iterates may be present in the telemetry; verify its
> sampling semantics before drawing quantitative conclusions.

---

## 🧪 Testing

```powershell
python -m unittest discover -s tests -v
```

Ten offline tests use real localhost sockets with mock simulator services (no APS needed):

| Transport | Test | Validates |
|---|---|---|
| UDP | Command mapping and bounds | Logical → wire keys; out-of-range and non-finite inputs rejected |
| UDP | Scalar commands | Single-input DLL format |
| UDP | Acquisition and restore | Invalid packets alongside valid telemetry; snapshot restored |
| UDP | Failure recovery | Snapshot restored when `RunDynamics` fails |
| UDP | Endpoint check | Wrong final telemetry time rejected |
| TCP v2 | Acquisition with acknowledgement | Accepted-step samples, ack, endpoint |
| TCP v2 | Steady state | `run.settle` extends the run until the drift is below tolerance |
| TCP v2 | Rejected step | Samples invalidated by a `rewind` removed; no false "lost sample" |
| TCP v2 | DLL reload | Reconnection when a snapshot restore drops the connection |
| TCP v2 | Missing acknowledgement | Run fails and the snapshot is still restored |

> **Status:** both transports are tested offline. The TCP v2 path was also run end to end in APS
> with the four-tank model and `config/four_tanks_tcp.json`: one constant-input run with `run.settle`
> succeeded after 3000 s of simulated time (2000 s plus two 500 s extensions) in 32 s of wall time,
> with 30 000 accepted-step samples, no sequence gaps, no repeated times, the command acknowledged
> by the DLL and the snapshot restored afterwards.

---

## 🔧 Troubleshooting

<details>
<summary><strong>simcentralconnect import fails</strong></summary>

Use the Python environment where AVEVA's connector is installed. Do not copy vendor DLLs into this repository or assume an arbitrary PyPI package is the correct connector. The connector is tied to your specific APS installation.
</details>

<details>
<summary><strong>PowerShell mangles the JSON in --inputs</strong></summary>

PowerShell's native argument handling can alter JSON quoting. Either:
- Add `example_inputs` to your config JSON and omit `--inputs`
- Use `cmd.exe` instead of PowerShell
- Escape with triple quotes: `--inputs '{\"feed_1\": 0.08}'`
</details>

<details>
<summary><strong>UDP receiver times out (no telemetry)</strong></summary>

1. Verify the DLL is deployed and AVEVA is in Dynamics mode
2. Check that UDP port 5005 is not in use by another program
3. Confirm `peer_ip` and `send_port` match the DLL's send configuration
4. Start the experiment **after** AVEVA has fully loaded the model
</details>

<details>
<summary><strong>Snapshot does not fully reset state</strong></summary>

APS snapshots may not reset private DLL memory or queued UDP commands. With UDP the engine drains residual telemetry and sends a complete input vector, but cannot guarantee a protocol-level reset. The TCP v2 bridge detects restores (`rewind`) and the engine verifies the acknowledgement of each command.
</details>

<details>
<summary><strong>TCP v2: connection lost after the first snapshot restore</strong></summary>

In a freshly opened simulation the first restore can reload the DLL, which closes the TCP connection. The engine connects the bridge **after** the restore and reconnects automatically when the link no longer answers.
</details>

<details>
<summary><strong>Steady state computed by APS ignores the DLL inputs</strong></summary>

`SolveSteadyStateDynamics` does not re-evaluate external equations, so the inputs held by the DLL are ignored. Obtain steady states by integration until the outputs settle (`run.settle`).
</details>

<details>
<summary><strong>Data lost or RunDynamics returns immediately</strong></summary>

Always use `.Result` on `RunDynamics` (otherwise the call is asynchronous), and call `OpenSimulation(...).Result` in each API session: an open GUI does not count as an open simulation for the API.
</details>

<details>
<summary><strong>RunDynamics duration vs. target time confusion</strong></summary>

Verify whether your installed `RunDynamics` interprets its argument as a duration or an absolute target time before changing starting clocks. The engine passes the configured `argument` value directly — it does not guess the semantics from .NET type names.
</details>

---

## 🚀 What Can Be Reused?

The engine supports **any configured number of numeric inputs and outputs** when the custom DLL implements the selected protocol. Adapting to another process model requires:

1. Building and deploying a compatible DLL ([instructions here](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP))
2. Writing a JSON config with the new variable mappings, bounds, and run parameters
3. Preparing a Dynamics snapshot as the base state

No Python code changes are needed.

### Extension Roadmap

- **Soft Sensors** — Feed telemetry to ML models for real-time inference of unmeasured variables
- **Model Predictive Control** — Replace constant inputs with optimization-based sequences
- **AVEVA PI System** — Write experiment results to PI tags for historian storage
- **Dynamic Operability** — Implement the full input-sequence funnel propagation algorithm
- **Green Hydrogen** — Apply to electrolyzer/fuel cell models for H₂ production optimization

---

## ⚠️ Important Notes

- No module connects to APS merely when imported — side-effect free
- Keep your own multiprocessing entry points under `if __name__ == "__main__":` on Windows
- Use one engine/port pair sequentially — these examples do not coordinate concurrent access
- Units in configuration document the contract; the engine does **not** perform unit conversion

---

## 👤 Author

**Ezequiel José Valencia Urbina**

- 🎓 M.Sc. Candidate — Mechanical Systems Dynamics, University of Brasília (UnB)
- 🔬 Research: Digital Twins, Soft Sensors, Process Control, Green Hydrogen
- 🔗 Collaboration: [CODES Group](https://fernandolima.faculty.wvu.edu/) of Prof. Fernando V. Lima, West Virginia University
- 📧 urbina.ezequiel@aluno.unb.br

---

## 🙏 Acknowledgments

- **[Opyrability](https://github.com/CODES-group/opyrability)** — The operability analysis in this project is powered by the Opyrability package, developed by [Victor Alves](https://victor-alves.com), San Dinh, [John Kitchin](https://github.com/jkitchin), Vitor Gazzaneo, Juan C. Carrasco, and [Fernando V. Lima](https://github.com/fvlima-codes) at the [CODES Group](https://fernandolima.faculty.wvu.edu/) (Carnegie Mellon University / West Virginia University). Published in the [Journal of Open Source Software](https://doi.org/10.21105/joss.05966) (2024).

- **AVEVA** — AVEVA Process Simulation and the External Equation Toolkit (EETK) are products of AVEVA Group plc. The `simcentralconnect` API is part of the official AVEVA scripting infrastructure.

---

## 📝 License

No code license has been selected yet. AVEVA and third-party components remain subject to their own terms and are not redistributed here.

> **Recommendation:** Consider adding [MIT](https://choosealicense.com/licenses/mit/) or [Apache-2.0](https://choosealicense.com/licenses/apache-2.0/) for maximum academic and industrial reuse.

---

## 🌐 Related Repositories

| Repository | Description |
|------------|-------------|
| [AVEVA-Process-Simulation-UDP](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP) | C# DLL bridges (UDP v1 and TCP v2), EETK setup, installation video, PDF guide |
| [Opyrability (CODES-group)](https://github.com/CODES-group/opyrability) | Process operability package by Alves et al. — used for OI evaluation in this project |
| This repository | Python automation engine, sweeps, operability analysis |

---

<p align="center">
  <strong>Made with ❤️ at the University of Brasília (UnB)</strong><br>
  <em>Automating rigorous simulation for research and industry</em>
</p>
