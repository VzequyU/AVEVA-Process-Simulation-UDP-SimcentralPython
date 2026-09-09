<p align="center">
  <img src="https://img.shields.io/badge/AVEVA-Process%20Simulation-purple?style=for-the-badge&logo=data:image/png;base64," alt="AVEVA"/>
  <img src="https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/SimCentral-Connect%20API-teal?style=for-the-badge" alt="SimCentral"/>
  <img src="https://img.shields.io/badge/Protocol-UDP%20Sockets-orange?style=for-the-badge" alt="UDP"/>
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
- **Custom EETK DLL over UDP** — real-time bidirectional data exchange with the process model

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
- ✅ **Concurrent UDP** — receiver runs in a separate process, never blocks the solver
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
| `aveva_engine.py` | Core engine: configurable connection, snapshot reset, concurrent UDP reception, result logging |
| `run_experiment.py` | Run a single configured input vector |
| `test_aveva_engine.py` | Manual integration entry point for checking the connection |
| `automated_experiments.py` | Sequential constant-input grid experiments |
| `opyrability_oi.py` | Fixed-horizon input/output map and raw OI evaluation |

| Configuration | Purpose |
|---------------|---------|
| `config/four_tanks.json` | Concrete four-tank connection example |
| `config/generic_valve.template.json` | Starting template for another process (edit before use) |
| `config/grid_four_tanks.json` | Nine-trial grid example |
| `config/operability_four_tanks.json` | Illustrative two-level DOS and resolution |

| Support | Purpose |
|---------|---------|
| `tests/test_engine_offline.py` | Offline tests with real UDP sockets and mock APS services |
| `docs/` | Connection instructions, protocol details, adaptation guide, LaTeX guide |

---

## 🚀 Quick Start

### Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| AVEVA Process Simulation | 2023+ | Process simulator with EETK |
| Python | 3.8+ | With `simcentralconnect` working |
| Custom EETK DLL | Compatible | Deployed in your APS model ([build it here](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP)) |
| NumPy + Opyrability | Optional | Only for `opyrability_oi.py` |

> ⚠️ Use the Windows Python environment where `import simcentralconnect` and `simcentralconnect.connect().Result` already work. Obtain the connector through your installed product's supported setup.

### Step 1 — Prepare the Simulation

Open your process model, deploy its custom DLL, verify variable specifications, and prepare a named snapshot in Dynamics mode. Stop other programs using UDP port 5005.

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

> **Note:** Logical input `feed_1` maps to DLL wire key `q1`; logical output `level_1` maps to telemetry key `h1`. Changing a JSON key here does **not** create a variable in the DLL — new process variables must be bound and serialized in the C# code.

### Step 3 — Check One Experiment

```powershell
# Default input vector from config
python -u test_aveva_engine.py --config config/four_tanks.json

# Custom input vector
python -u run_experiment.py --config config/four_tanks.json --inputs '{"feed_1": 0.08, "feed_2": 0.05}'
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

Evaluate a fixed-horizon operability index using the [Opyrability](https://github.com/opyrability/opyrability) package:

```powershell
python -u opyrability_oi.py --config config/four_tanks.json --study config/operability_four_tanks.json
```

The script:
1. Builds a `model(u) → y` function backed by the APS engine
2. Caches evaluations to avoid re-simulating visited points
3. Calls `multimodel_rep` to construct the achievable output set (AOS)
4. Calls `OI_eval` against the desired output set (DOS) to compute the raw OI

> ⚠️ This is a **constant-input, fixed-horizon map**. A full dynamic operability funnel requires propagation from retained complete states under changing input sequences. See [docs/operability.md](docs/operability.md).

---

## 📋 Results and Validation

Every run creates a unique directory under `results/`:

```
results/
└── a1b2c3d4.../
    ├── telemetry.jsonl    # Raw UDP packets (receive order, including malformed)
    └── result.json        # Config, inputs, outputs, timing, cleanup status
```

**What `success: true` means:**
- ✅ APS `RunDynamics` returned success
- ✅ Usable telemetry reached the expected clock within tolerance
- ✅ Post-run cleanup (stop + snapshot restore) succeeded

**What it does NOT prove:**
- ❌ Command acknowledgement (DLL has no ACK protocol)
- ❌ Accepted-step sampling (intermediate solver iterates may be present)
- ❌ Complete DLL state reset (snapshot may not reset private DLL memory)

> Verify the DLL's sampling semantics before drawing quantitative reachability conclusions. See [docs/protocol.md](docs/protocol.md).

---

## 🧪 Testing

```powershell
python -m unittest discover -s tests -v
```

Five offline tests pass using real localhost UDP with mock simulator services:

| Test | Validates |
|------|-----------|
| Command mapping | JSON encoding with logical → wire key translation |
| Bounds rejection | Out-of-range inputs are caught before sending |
| Scalar commands | Single-input DLL format works correctly |
| Concurrent UDP | Receiver handles invalid packets alongside valid telemetry |
| Failure recovery | Snapshot is restored even when `RunDynamics` fails |
| Endpoint check | Incorrect final telemetry time is detected and rejected |

> **Status:** This refactored version has been tested offline. It has **not yet been executed against a live APS installation**.

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

APS snapshots may not reset private DLL memory or queued UDP commands. The engine drains residual telemetry and sends a complete input vector, but cannot guarantee a protocol-level reset without DLL-side support. See [docs/protocol.md](docs/protocol.md).
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

No Python code changes are needed. See [docs/adapt_another_simulation.md](docs/adapt_another_simulation.md).

### Extension Roadmap

- **Soft Sensors** — Feed telemetry to ML models for real-time inference of unmeasured variables
- **Model Predictive Control** — Replace constant inputs with optimization-based sequences
- **AVEVA PI System** — Write experiment results to PI tags for historian storage
- **Dynamic Operability** — Implement the full input-sequence funnel propagation algorithm
- **Green Hydrogen** — Apply to electrolyzer/fuel cell models for H₂ production optimization
- **Refinery Inference** — Deploy trained models for distillation column quality prediction

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
- 🔗 Petrobras collaboration: real-time inference in petroleum refineries
- 📧 urbina.ezequiel@aluno.unb.br

---

## 📝 License

No code license has been selected yet. AVEVA and third-party components remain subject to their own terms and are not redistributed here.

> **Recommendation:** Consider adding [MIT](https://choosealicense.com/licenses/mit/) or [Apache-2.0](https://choosealicense.com/licenses/apache-2.0/) for maximum academic and industrial reuse.

---

## 🌐 Related Repositories

| Repository | Description |
|------------|-------------|
| [AVEVA-Process-Simulation-UDP](https://github.com/VzequyU/AVEVA-Process-Simulation-UDP) | C# DLL development, EETK setup, valve and four-tank examples, PDF guide |
| This repository | Python automation engine, sweeps, operability analysis |

---

<p align="center">
  <strong>Made with ❤️ at the University of Brasília (UnB)</strong><br>
  <em>Automating rigorous simulation for research and industry</em>
</p>
