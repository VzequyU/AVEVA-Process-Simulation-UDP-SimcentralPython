# Changes from the supplied scripts

- `AVEVAEngine(config)` validates configuration; `.connect()` explicitly opens the connection. No constructor binds a UDP port or starts APS.
- `run(inputs)` replaces the hard-coded `ejecutar(q1, q2, horizonte)` interface. The run timing belongs to the configuration.
- Input/output logical names map to arbitrary DLL message keys. `enviar_q` and the fixed list of four levels are no longer built into the engine.
- Reception runs in a spawned process during APS execution, rather than reading a finite buffer after execution.
- Each experiment writes raw telemetry and a status record, including on failure, and attempts stop/reset in cleanup.
- The Opyrability module no longer connects or runs a study at import time. It uses the configurable outputs and does not assert an unverified OI percentage convention.
- Old callers are not drop-in compatible. Use the new command-line examples or update your callers to `.connect().run(...)`.

The earlier guide contains conceptual runner methods. The executable implementation in this revision is `AVEVAEngine.run`; follow the repository README for its concrete API.
