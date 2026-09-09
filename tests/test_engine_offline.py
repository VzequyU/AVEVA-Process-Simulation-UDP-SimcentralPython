"""Real localhost UDP with fake APS services; no proprietary installation needed."""
import json
import socket
import tempfile
import unittest
from pathlib import Path
from aveva_engine import AVEVAEngine, encode_inputs, load_config, validate_config
ROOT = Path(__file__).resolve().parents[1]

class Task:
    def __init__(self, value): self.Result = value

class Snapshots:
    def __init__(self): self.restores = 0
    def RevertSnapshot(self, *args):
        self.restores += 1
        return Task(True)

class Simulator:
    def __init__(self, config, fail=False):
        self.fail = fail
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))
        config['udp']['send_port'] = self.sock.getsockname()[1]
        self.sock.settimeout(5)
    def TriggerStopSolve(self, *args): return Task(True)
    def GetSimulationMode(self, *args): return Task('Dynamics')
    def RunDynamics(self, *args):
        payload, peer = self.sock.recvfrom(65535)
        self.command = json.loads(payload)
        if self.fail: return Task(False)
        self.sock.sendto(b'not-json', peer)
        for t in (1., 20.):
            packet = {'sim_time': t, 'h1': .18, 'h2': .17, 'h3': .07, 'h4': .08}
            self.sock.sendto(json.dumps(packet).encode(), peer)
        return Task(True)

class EngineTests(unittest.TestCase):
    def config(self):
        c = load_config(ROOT / 'config/four_tanks.json')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0))
            c['udp']['receive_port'] = sock.getsockname()[1]
        return c
    def test_mapping_and_input_rejection(self):
        c = self.config()
        self.assertEqual(json.loads(encode_inputs(c, {'feed_1': .08, 'feed_2': .05})), {'q1': .08, 'q2': .05})
        for values in ({'feed_1': .5, 'feed_2': .05}, {'feed_1': float('nan'), 'feed_2': .05}, {'q1': .08}):
            with self.assertRaises(ValueError): encode_inputs(c, values)
    def test_scalar_contract(self):
        c = self.config()
        c['inputs'] = {'opening': {'key': 'u', 'unit': 'fraction', 'bounds': [0, 1]}}
        c['udp']['command_format'] = 'scalar'
        self.assertEqual(encode_inputs(validate_config(c), {'opening': .5}), b'0.5')
    def execute_case(self, fail=False, wrong_time=False):
        c = self.config()
        if wrong_time: c['run']['expected_final_time'] = 30.
        with tempfile.TemporaryDirectory() as directory:
            c['result_directory'] = directory
            sim = Simulator(c, fail)
            engine = AVEVAEngine(c)
            engine.sm, engine.snap = sim, Snapshots()
            try:
                if fail or wrong_time:
                    with self.assertRaises(RuntimeError): engine.run(c['example_inputs'])
                else:
                    record = engine.run(c['example_inputs'])
                    self.assertTrue(record['success'])
                    self.assertFalse(record['command_applied_verified'])
                    self.assertEqual(record['outputs']['level_1'], .18)
                    self.assertEqual(record['telemetry']['invalid'], 1)
                    self.assertEqual(record['telemetry']['packets'], 2)
                    self.assertEqual(sim.command, {'q1': .08, 'q2': .05})
                self.assertEqual(engine.snap.restores, 2)
                saved = list(Path(directory).glob('*/result.json'))
                self.assertEqual(len(saved), 1)
                self.assertEqual(json.loads(saved[0].read_text())['success'], not (fail or wrong_time))
            finally: sim.sock.close()
    def test_udp_acquisition_and_restore(self): self.execute_case()
    def test_run_failure_still_restores(self): self.execute_case(fail=True)
    def test_wrong_endpoint_is_rejected(self): self.execute_case(wrong_time=True)

if __name__ == '__main__': unittest.main()
