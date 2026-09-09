# Setup and first run

## Local prerequisites

Keep the APS installation, vendor DLLs and `simcentralconnect` environment on the Windows host. Do not copy the complete AVEVA installation into this repository. Obtain EETK and scripting dependencies through the installed product and its supported distribution process.

The custom UDP DLL and the APS model must agree on variable bindings, units, port numbers and wire format. Refer to the author's separate bridge repository and the guide; neither the model nor a compiled custom DLL is included in this starter.

## Configure the script

| Constant | Default | Meaning |
|---|---|---|
| `SIM_NAME` | `Sim 3` | Exact APS simulation name. |
| `SNAPSHOT_NAME` | `start dym` | Prepared Dynamics snapshot. |
| `Q1`, `Q2` | `0.08`, `0.05` | Commanded inlet flows in kg/s. |
| `RUN_ARGUMENT_S` | `20.0` | Run argument; verify clock semantics in APS. |
| `IP` | `127.0.0.1` | Local communication address. |
| `RECEIVE_PORT` | `5005` | Python receiver port. |
| `SEND_PORT` | `5006` | DLL command port. |
| `API_TIMEOUT_MS` | `120000` | API timeout configuration. |

Run one simulation client at a time using this port pair. The acquisition process owns the bound receive socket and sends the input command from that same socket.

## What to inspect

Check that the mode is Dynamics, `RunDynamics` succeeds, telemetry arrives, the last time matches the intended endpoint, and the outputs respond. Inspect stop and restoration outcomes separately. Printing `GetSimulationTimeDetails` may display only a .NET type name; it does not by itself validate the clock fields.

A receiver error is currently reported in the summary and must be treated as an unsuccessful acquisition even if APS ran. Snapshot restoration may not clear private DLL command buffers. Check applied inputs and initial state when repeating trials.

## Opyrability environment

Follow the diagnostic in the guide to print the imported package path, distribution version and function signatures. Install the specific revision required for the project using its instructions. This starter deliberately does not claim an unverified set of dependency pins or provide a guessed `pip install` command for the AVEVA connector.
