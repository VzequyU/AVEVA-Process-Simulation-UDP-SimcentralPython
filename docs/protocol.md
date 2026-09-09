# UDP and lifecycle protocol

The UDP worker runs in a separate Python process while the parent waits on `RunDynamics(...).Result`. It owns one socket, bound to the configured receive address and port, and sends commands from that same socket to the DLL command port.

For the four-tank example: Python receives at `127.0.0.1:5005`, and the DLL receives at `127.0.0.1:5006`. Match these endpoints on both sides. JSON messages are flat UTF-8 objects. Plain numeric commands are supported only for a single input; telemetry must still be JSON.

Only finite numeric values are used as measurements. Unknown fields are retained in the raw message but ignored by output extraction. The worker streams datagrams to disk and returns a small summary; it does not put entire trajectories into multiprocessing queues. Source filtering uses the configured peer IP; it is not authentication.

The parent controls APS through these demonstrated calls:

```python
sc = simcentralconnect.connect().Result
sm = sc.GetService("ISimulationManager")
snap = sc.GetService("ISnapshotManager")
sm.OpenSimulation(sim_name, timeout_ms).Result
sm.TriggerStopSolve(sim_name, timeout_ms).Result
snap.RevertSnapshot(sim_name, snapshot_name, timeout_ms).Result
sm.GetSimulationMode(sim_name, timeout_ms).Result
sm.RunDynamics(sim_name, run_argument, "s").Result
```

The final stop must succeed before restoration is attempted. Failures are raised and recorded. The original run error is preserved if cleanup also fails.

Current limitations: no command acknowledgements, run identifiers, sequence numbers, bridge-reset handshake or proof of accepted solver states. Repeated/backward clock samples are counted, not sorted away. The engine chooses the last usable received observation and verifies its clock; that is weaker than verifying an accepted simulator endpoint.

For stronger experiments, extend both DLL and Python with command application identity, run identity, applied input values and accepted-state telemetry. A paused DLL may only consume a command when dynamics begins, so do not assume a paused acknowledgement is possible.
