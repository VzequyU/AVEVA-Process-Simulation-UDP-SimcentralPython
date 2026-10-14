"""TCP client for the version-2 EETK bridge (one sample per accepted step, acknowledged commands).

Copied from the DLL repository (AVEVA-Process-Simulation-UDP, v2_tcp/python/aveva_bridge_v2.py),
without its quadruple-tank engine class; AVEVAEngine in aveva_engine.py uses it when the
configuration selects "transport": "tcp_v2".

Protocol: one JSON object per line.
  Python -> DLL : {"cmd":"set","id":n,<key>:value,...,"apply":"step"|"now"}, flush, ping, status
  DLL -> Python : hello, queued, ack, sample, rewind, superseded, flushed, pong, status, error
"""
from __future__ import annotations

import json
import queue
import socket
import threading
import time
from typing import Dict, List, Optional


class BridgeError(RuntimeError):
    pass


class BridgeV2:
    def __init__(self, host: str = "127.0.0.1", port: int = 5006, timeout: float = 5.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock: Optional[socket.socket] = None
        self.inbox: "queue.Queue[dict]" = queue.Queue()
        self.hello: Optional[dict] = None
        self._next_id = 0
        self._reader: Optional[threading.Thread] = None
        self._closed = threading.Event()
        self.bad_lines = 0
        self._held: List[dict] = []   # messages skipped by wait_for; returned by drain()

    # ------------------------------------------------------------ connection
    def connect(self, retries: int = 50, wait: float = 0.1) -> "BridgeV2":
        last = None
        for _ in range(retries):
            try:
                self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                break
            except OSError as exc:
                last = exc
                time.sleep(wait)
        if self.sock is None:
            raise BridgeError(f"cannot connect to {self.host}:{self.port}: {last}")
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(None)
        self._closed.clear()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self.hello = self.wait_for("hello", timeout=self.timeout)
        return self

    def close(self) -> None:
        self._closed.set()
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
            self.sock = None

    def _read_loop(self) -> None:
        buf = b""
        try:
            while not self._closed.is_set():
                chunk = self.sock.recv(1 << 16)
                if not chunk:
                    break
                buf += chunk
                *lines, buf = buf.split(b"\n")
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        self.bad_lines += 1
                        continue
                    msg["_rx"] = time.perf_counter()
                    self.inbox.put(msg)
        except OSError:
            pass
        finally:
            self.inbox.put({"type": "_disconnected"})

    # ------------------------------------------------------------ messaging
    def send(self, obj: dict) -> None:
        if self.sock is None:
            raise BridgeError("not connected")
        self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def set_values(self, apply: str = "step", confirm: bool = True,
                   keep: Optional[List[dict]] = None, **values: float) -> int:
        """Queue new actuator values by name (e.g. XV1pos=0.3, RebHeat=0.82).

        apply='step' -> at the next step boundary; 'now' -> at the next evaluation.
        With confirm=True the call returns only after the DLL has the command in its queue, so
        a solver run started afterwards applies it at its first evaluation (no race).
        """
        self._next_id += 1
        cid = self._next_id
        msg = {"cmd": "set", "id": cid, "apply": apply}
        msg.update({k: float(v) for k, v in values.items() if v is not None})
        self.send(msg)
        if confirm:
            self.wait_for("queued", timeout=self.timeout, keep=keep,
                          match=lambda m: str(m.get("id")) == str(cid))
        return cid

    def set_inputs(self, q1: Optional[float] = None, q2: Optional[float] = None,
                   apply: str = "step", confirm: bool = True,
                   keep: Optional[List[dict]] = None) -> int:
        """Quadruple tank: flows q1, q2."""
        return self.set_values(apply=apply, confirm=confirm, keep=keep, q1=q1, q2=q2)

    def drain(self) -> List[dict]:
        out, self._held = self._held, []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def wait_for(self, mtype: str, timeout: float = 5.0, keep: Optional[List[dict]] = None,
                 match=None) -> dict:
        """Return the first message of type mtype. Other messages are appended to keep or, if
        keep is None, held and returned by the next drain(): nothing is ever discarded."""
        end = time.perf_counter() + timeout
        while True:
            left = end - time.perf_counter()
            if left <= 0:
                raise BridgeError(f"timeout waiting for '{mtype}'")
            try:
                msg = self.inbox.get(timeout=left)
            except queue.Empty:
                continue
            if msg.get("type") == "_disconnected":
                raise BridgeError("bridge disconnected")
            if msg.get("type") == mtype and (match is None or match(msg)):
                return msg
            (keep if keep is not None else self._held).append(msg)

    def ping(self) -> float:
        t0 = time.perf_counter()
        self.send({"cmd": "ping", "id": 0})
        self.wait_for("pong")
        return time.perf_counter() - t0

    def status(self) -> dict:
        self.send({"cmd": "status"})
        return self.wait_for("status")

    def flush(self, keep: List[dict], timeout: float = 5.0) -> None:
        """After RunDynamics returns: emit the (converged) last step and wait for confirmation."""
        self.send({"cmd": "flush"})
        self.wait_for("flushed", timeout=timeout, keep=keep)


# ---------------------------------------------------------------- integrity checks
def validate(samples: List[dict], dt_nominal: Optional[float] = None) -> Dict[str, object]:
    seqs = [s["seq"] for s in samples]
    ts = [s["t"] for s in samples]
    gaps = [(a, b) for a, b in zip(seqs, seqs[1:]) if b != a + 1]
    non_increasing = [(a, b) for a, b in zip(ts, ts[1:]) if b <= a]
    evals = [s.get("evals", 0) for s in samples]
    rep = {
        "n_samples": len(samples),
        "seq_gaps": gaps[:20],
        "n_seq_gaps": len(gaps),
        "non_increasing_t": non_increasing[:20],
        "n_non_increasing_t": len(non_increasing),
        "evals_per_step_mean": (sum(evals) / len(evals)) if evals else None,
        "evals_per_step_max": max(evals) if evals else None,
    }
    if dt_nominal and len(ts) > 1:
        dts = [b - a for a, b in zip(ts, ts[1:])]
        rep["dt_min"], rep["dt_max"] = min(dts), max(dts)
        rep["n_dt_off_nominal"] = sum(abs(d - dt_nominal) > 1e-6 for d in dts)
    rep["ok"] = rep["n_seq_gaps"] == 0 and rep["n_non_increasing_t"] == 0
    return rep
