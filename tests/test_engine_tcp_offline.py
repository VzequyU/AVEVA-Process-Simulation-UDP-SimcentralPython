"""tcp_v2 transport with a fake bridge-v2 DLL (real localhost TCP) and fake APS services."""
import json
import math
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from aveva_engine import AVEVAEngine, load_config
ROOT = Path(__file__).resolve().parents[1]
DT = 0.5


class Task:
    def __init__(self, value): self.Result = value


class FakeBridgeDLL:
    """Speaks the v2 protocol: hello, queued, ack at the first step boundary, one sample per
    accepted step, flushed. Levels approach 2*q with time constant tau (first order)."""
    def __init__(self, tau=5.0, ack=True):
        self.tau, self.ack = tau, ack
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', 0))
        self.server.listen(4)
        self.port = self.server.getsockname()[1]
        self.lock = threading.Lock()
        self.conn = None
        self.pending = None
        self.q = {'q1': .05, 'q2': .05}
        self.h = {'h1': .1, 'h2': .1, 'h3': .1, 'h4': .1}
        self.t, self.seq, self.connections = 0.0, 0, 0
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with self.lock:
                self.conn = conn
                self.connections += 1
            self._send({'type': 'hello', 'version': 'fake-v2'})
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()

    def _send(self, msg):
        with self.lock:
            if self.conn is not None:
                try:
                    self.conn.sendall((json.dumps(msg) + '\n').encode())
                except OSError:
                    pass

    def _read(self, conn):
        buf = b''
        while True:
            try:
                chunk = conn.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            *lines, buf = buf.split(b'\n')
            for line in lines:
                msg = json.loads(line)
                if msg['cmd'] == 'set':
                    self.pending = msg
                    self._send({'type': 'queued', 'id': msg['id']})
                elif msg['cmd'] == 'flush':
                    self._send({'type': 'flushed'})
                elif msg['cmd'] == 'ping':
                    self._send({'type': 'pong', 'id': msg.get('id')})

    def drop_connection(self):
        """A snapshot restore that reloads the DLL closes the client connection."""
        with self.lock:
            if self.conn is not None:
                self.conn.close()
                self.conn = None

    def advance(self, duration, rewind_at=None):
        t_target, k = self.t + duration, -1
        while self.t < t_target - 1e-9:      # a rejected step is repeated, as by the solver
            k += 1
            if self.pending is not None:
                cmd, self.pending = self.pending, None
                self.q.update({key: cmd[key] for key in ('q1', 'q2') if key in cmd})
                if self.ack:
                    self._send({'type': 'ack', 'id': cmd['id'], 't': self.t + DT, 'reason': 'step'})
            self.t += DT
            a = math.exp(-DT / self.tau)
            for i, key in enumerate(('h1', 'h2', 'h3', 'h4')):
                target = 2 * self.q['q1' if i % 2 == 0 else 'q2']
                self.h[key] = target + (self.h[key] - target) * a
            self.seq += 1
            self._send({'type': 'sample', 'seq': self.seq, 't': self.t, **self.q, **self.h})
            if rewind_at is not None and k == rewind_at:
                # rejected step: time goes back one step, the solver repeats it
                self._send({'type': 'rewind', 'from': self.t, 'to': self.t - DT})
                self.t -= DT

    def close(self):
        self.drop_connection()
        self.server.close()


class Simulator:
    def __init__(self, dll, rewind_at=None):
        self.dll, self.rewind_at, self.runs = dll, rewind_at, 0
    def TriggerStopSolve(self, *args): return Task(True)
    def GetSimulationMode(self, *args): return Task('Dynamics')
    def RunDynamics(self, sim, duration, unit):
        self.runs += 1
        self.dll.advance(duration, self.rewind_at if self.runs == 1 else None)
        return Task(True)


class Snapshots:
    def __init__(self, dll, drop_on_first=False):
        self.dll, self.drop, self.restores = dll, drop_on_first, 0
    def RevertSnapshot(self, *args):
        self.restores += 1
        self.dll.t = 0.0
        self.dll.h = {k: .1 for k in self.dll.h}
        if self.drop and self.restores == 1:
            self.dll.drop_connection()
        return Task(True)


class TcpEngineTests(unittest.TestCase):
    def config(self, dll, settle=False):
        c = load_config(ROOT / 'config/four_tanks_tcp.json')
        c['tcp']['port'] = dll.port
        c['run']['argument'] = 20.0
        if not settle:
            c['run'].pop('settle', None)
        return c

    def run_case(self, dll, settle=False, rewind_at=None, drop=False, expect_error=False):
        c = self.config(dll, settle)
        with tempfile.TemporaryDirectory() as directory:
            c['result_directory'] = directory
            engine = AVEVAEngine(c)
            engine.sm = Simulator(dll, rewind_at)
            engine.snap = Snapshots(dll, drop)
            try:
                if expect_error:
                    with self.assertRaises(RuntimeError):
                        engine.run(c['example_inputs'])
                    return None, engine
                record = engine.run(c['example_inputs'])
                saved = json.loads(next(Path(directory).glob('*/result.json')).read_text())
                self.assertTrue(saved['success'])
                lines = next(Path(directory).glob('*/telemetry.jsonl')).read_text().splitlines()
                self.assertEqual(len(lines), record['telemetry']['samples'])
                return record, engine
            finally:
                engine.close()

    def test_acquisition_with_acknowledgement(self):
        dll = FakeBridgeDLL()
        try:
            record, engine = self.run_case(dll)
            self.assertTrue(record['command_applied_verified'])
            self.assertEqual(record['telemetry']['samples'], 40)
            self.assertTrue(record['telemetry']['integrity']['ok'])
            self.assertAlmostEqual(record['outputs']['level_1'], .16, places=2)
            self.assertEqual(engine.snap.restores, 2)
        finally:
            dll.close()

    def test_settle_extends_until_drift_is_small(self):
        dll = FakeBridgeDLL(tau=30.0)
        try:
            record, engine = self.run_case(dll, settle=True)
            self.assertTrue(record['settled'])
            self.assertGreater(record['simulated_seconds'], 20.0)
            self.assertAlmostEqual(record['outputs']['level_1'], .16, places=3)
        finally:
            dll.close()

    def test_rewind_removes_invalid_samples(self):
        dll = FakeBridgeDLL()
        try:
            record, _ = self.run_case(dll, rewind_at=10)
            integrity = record['telemetry']['integrity']
            self.assertTrue(integrity['ok'])
            self.assertEqual(integrity['samples_removed_by_rewind'], 1)
            self.assertEqual(integrity['n_lost'], 0)
            self.assertEqual(len([e for e in record['telemetry']['events'] if e['type'] == 'rewind']), 1)
        finally:
            dll.close()

    def test_reconnects_after_dll_reload(self):
        dll = FakeBridgeDLL()
        try:
            c = self.config(dll)
            with tempfile.TemporaryDirectory() as directory:
                c['result_directory'] = directory
                engine = AVEVAEngine(c)
                engine.sm, engine.snap = Simulator(dll), Snapshots(dll, drop_on_first=True)
                engine._bridge()                      # connected before the first restore
                record = engine.run(c['example_inputs'])
                engine.close()
            self.assertTrue(record['success'])
            self.assertEqual(dll.connections, 2)
        finally:
            dll.close()

    def test_missing_acknowledgement_fails_and_restores(self):
        dll = FakeBridgeDLL(ack=False)
        try:
            _, engine = self.run_case(dll, expect_error=True)
            self.assertEqual(engine.snap.restores, 2)
        finally:
            dll.close()


if __name__ == '__main__':
    unittest.main()
