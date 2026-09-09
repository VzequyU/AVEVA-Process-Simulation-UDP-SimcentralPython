# Existing four-tank UDP protocol

Transport: UDP on localhost. Encoding: UTF-8 JSON.

Python sends to the DLL at port 5006:

```json
{"q1": 0.08, "q2": 0.05}
```

The DLL sends measurements to Python at port 5005:

```json
{"sim_time": 20.0, "h1": 0.1805, "h2": 0.1725, "h3": 0.0747, "h4": 0.0782}
```

Flows are kg/s, levels are m and the tested simulation clock is expressed in seconds. Validate the bindings in the actual model.

The current format has no run ID, command ID, applied-input acknowledgement or sequence number. These are proposed future additions and require changes to both Python and the DLL. A plain-string valve DLL uses a different contract and cannot receive these JSON commands without adaptation.
