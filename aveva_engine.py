"""Configurable APS lifecycle + UDP (v1) or TCP (v2) transport. Importing has no side effects."""
import copy
import json
import math
import multiprocessing as mp
import socket
import time
import uuid
from pathlib import Path


def finite(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a process measurement')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Expected a finite number')
    return value


def validate_config(config):
    c = copy.deepcopy(config)
    c.setdefault('transport', 'udp')
    if c['transport'] not in ('udp', 'tcp_v2'):
        raise ValueError('transport must be udp or tcp_v2')
    for key in ('simulation', 'snapshot', 'inputs', 'outputs', 'run',
                'udp' if c['transport'] == 'udp' else 'tcp'):
        if not c.get(key):
            raise ValueError(f'Missing configuration: {key}')
    for group in ('inputs', 'outputs'):
        names = []
        for name, signal in c[group].items():
            names.append(signal['key'])
            if not signal.get('unit'):
                raise ValueError(f'Missing unit: {name}')
        if len(names) != len(set(names)):
            raise ValueError(f'Duplicate wire keys in {group}')
    for name, signal in c['inputs'].items():
        lo, hi = map(finite, signal['bounds'])
        if lo >= hi:
            raise ValueError(f'Invalid input bounds: {name}')
    if c['transport'] == 'udp':
        udp = c['udp']
        for key in ('receive_port', 'send_port'):
            if not isinstance(udp[key], int) or not 1 <= udp[key] <= 65535:
                raise ValueError(f'Invalid port: {key}')
        socket.inet_aton(udp['bind_ip'])
        socket.inet_aton(udp['peer_ip'])
        if udp['command_format'] not in ('json', 'scalar'):
            raise ValueError('command_format must be json or scalar')
        if udp['command_format'] == 'scalar' and len(c['inputs']) != 1:
            raise ValueError('Scalar format requires exactly one input')
    else:
        tcp = c['tcp']
        tcp.setdefault('host', '127.0.0.1')
        tcp.setdefault('timeout', 5.0)
        tcp.setdefault('apply', 'step')
        socket.inet_aton(tcp['host'])
        if not isinstance(tcp.get('port'), int) or not 1 <= tcp['port'] <= 65535:
            raise ValueError('Invalid tcp port')
        if tcp['apply'] not in ('step', 'now'):
            raise ValueError('tcp apply must be step or now')
        if finite(tcp['timeout']) <= 0:
            raise ValueError('Invalid tcp timeout')
    settle = c['run'].get('settle')
    if settle is not None:
        if c['transport'] != 'tcp_v2':
            raise ValueError('run.settle requires the tcp_v2 transport (one sample per accepted step)')
        for key in ('chunk', 'max_time', 'window', 'tolerance'):
            if finite(settle[key]) <= 0:
                raise ValueError(f'Invalid run.settle {key}')
        if settle['window'] > settle['chunk'] + c['run']['argument']:
            raise ValueError('run.settle window must fit inside the simulated time')
    if c['run']['unit'] != 's':
        raise ValueError('This runner requires run argument and telemetry time in seconds')
    for key in ('argument', 'time_tolerance'):
        if finite(c['run'][key]) <= 0:
            raise ValueError(f'Invalid run {key}')
    finite(c['run']['expected_final_time'])
    if not c['run'].get('time_key'):
        raise ValueError('A telemetry time key is required')
    for key, default in (('worker_timeout', 15), ('drain_seconds', .3)):
        c.setdefault(key, default)
        if finite(c[key]) <= 0:
            raise ValueError(f'Invalid {key}')
    c.setdefault('api_timeout_ms', 120000)
    if int(c['api_timeout_ms']) <= 0:
        raise ValueError('api_timeout_ms must be positive')
    c.setdefault('result_directory', 'results')
    return c


def load_config(filename):
    with open(filename, encoding='utf-8') as stream:
        return validate_config(json.load(stream))


def encode_inputs(config, inputs):
    if set(inputs) != set(config['inputs']):
        raise ValueError('Supply exactly the configured input names')
    values = {}
    for name, signal in config['inputs'].items():
        value = finite(inputs[name])
        lo, hi = signal['bounds']
        if not lo <= value <= hi:
            raise ValueError(f'{name} outside [{lo}, {hi}]')
        values[signal['key']] = value
    if config.get('transport', 'udp') == 'udp' and config['udp']['command_format'] == 'scalar':
        return str(next(iter(values.values()))).encode('utf-8')
    return json.dumps(values, allow_nan=False).encode('utf-8')


def _receiver(config, commands, status, stop, filename):
    """One socket owner; stream packets to disk, return only a small summary."""
    summary = {'packets': 0, 'invalid': 0, 'backwards': 0, 'first_time': None,
               'last_time': None, 'endpoint': None, 'endpoint_outputs': None}
    previous = None
    try:
        net = config['udp']
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock, open(filename, 'w', encoding='utf-8') as log:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            sock.bind((net['bind_ip'], net['receive_port']))
            sock.settimeout(.02)
            # Remove datagrams queued before the experiment's command.
            sock.setblocking(False)
            deadline = time.monotonic() + .2
            while time.monotonic() < deadline:
                try:
                    sock.recvfrom(65535)
                except BlockingIOError:
                    break
            sock.settimeout(.02)
            status.send(('ready', None))
            if not commands.poll(config['worker_timeout']):
                raise TimeoutError('No input command supplied to UDP worker')
            payload = commands.recv()
            sock.sendto(payload, (net['peer_ip'], net['send_port']))
            status.send(('sent', None))  # Transport only, not an APS acknowledgement.
            while not stop.is_set():
                try:
                    raw, address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                if address[0] != net['peer_ip']:
                    continue
                # Preserve malformed packets too, without growing a memory queue.
                log.write(json.dumps({'received_monotonic': time.monotonic(),
                                      'payload': raw.decode('utf-8', errors='replace')}) + '\n')
                try:
                    packet = json.loads(raw.decode('utf-8'))
                    if not isinstance(packet, dict):
                        raise ValueError('Telemetry must be a JSON object')
                    stamp = finite(packet[config['run']['time_key']])
                    outputs = {name: finite(packet[spec['key']])
                               for name, spec in config['outputs'].items()}
                except (ValueError, TypeError, KeyError, UnicodeError):
                    summary['invalid'] += 1
                    continue
                summary['packets'] += 1
                if summary['first_time'] is None:
                    summary['first_time'] = stamp
                if previous is not None and stamp < previous:
                    summary['backwards'] += 1
                previous = stamp
                summary['last_time'] = stamp
                # Last received usable observation: do not sort away solver reversals.
                summary['endpoint'] = stamp
                summary['endpoint_outputs'] = outputs
        status.send(('summary', summary))
    except Exception as exc:
        status.send(('error', repr(exc)))
    finally:
        commands.close()
        status.close()


def _expect(connection, tag, timeout):
    if not connection.poll(timeout):
        raise TimeoutError(f'UDP worker did not report {tag}')
    received, data = connection.recv()
    if received != tag:
        raise RuntimeError(f'Expected UDP {tag}, received {received}: {data}')
    return data


class AVEVAEngine:
    """Explicit connect, one independent constant-input run per snapshot reset.

    Does not close the user's APS simulation. Not thread-safe; serialize runs.
    """
    def __init__(self, config):
        self.config = validate_config(config)
        self.sc = self.sm = self.snap = None
        self.bridge = None

    @staticmethod
    def _check(value, operation):
        if not bool(value):
            raise RuntimeError(f'APS returned False: {operation}')

    def connect(self):
        # Parent only: spawned UDP worker never imports the proprietary connector.
        import simcentralconnect
        c = self.config
        self.sc = simcentralconnect.connect().Result
        self.sc.SetOptions(json.dumps({'Timeout': c['api_timeout_ms'],
                                       'EnableApiLogging': 'false'}))
        self.sm = self.sc.GetService('ISimulationManager')
        self.snap = self.sc.GetService('ISnapshotManager')
        if c['simulation'] not in list(self.sm.GetOpenSimulations().Result):
            self._check(self.sm.OpenSimulation(c['simulation'], c['api_timeout_ms']).Result, 'open')
        return self

    def reset(self):
        if self.sm is None:
            raise RuntimeError('Call connect() before reset() or run()')
        c = self.config
        self._check(self.sm.TriggerStopSolve(c['simulation'], c['api_timeout_ms']).Result, 'stop')
        self._check(self.snap.RevertSnapshot(c['simulation'], c['snapshot'], c['api_timeout_ms']).Result, 'restore snapshot')

    def run(self, inputs):
        c = self.config
        if c['transport'] == 'tcp_v2':
            return self._run_tcp(inputs)
        payload = encode_inputs(c, inputs)
        if self.sm is None:
            raise RuntimeError('Call connect() first')
        directory = Path(c['result_directory']).resolve() / uuid.uuid4().hex
        directory.mkdir(parents=True)
        result = {'inputs': dict(inputs), 'configuration': c, 'success': False,
                  'validation_scope': 'API completion and UDP timestamp; not accepted-state or input-ack verification',
                  'command_applied_verified': False, 'cleanup_errors': []}
        worker = None
        primary_error = None
        ctx = mp.get_context('spawn')
        command_reader, command_writer = ctx.Pipe(duplex=False)
        status_reader, status_writer = ctx.Pipe(duplex=False)
        stop = ctx.Event()
        try:
            self.reset()
            mode = str(self.sm.GetSimulationMode(c['simulation'], c['api_timeout_ms']).Result)
            if mode.lower() != 'dynamics':
                raise RuntimeError(f'Snapshot must restore Dynamics mode; received {mode}')
            worker = ctx.Process(target=_receiver, args=(c, command_reader, status_writer, stop,
                                                        str(directory / 'telemetry.jsonl')))
            worker.start()
            command_reader.close()
            status_writer.close()
            _expect(status_reader, 'ready', c['worker_timeout'])
            command_writer.send(payload)
            _expect(status_reader, 'sent', c['worker_timeout'])
            started = time.perf_counter()
            self._check(self.sm.RunDynamics(c['simulation'], float(c['run']['argument']), 's').Result, 'run dynamics')
            result['wall_seconds'] = time.perf_counter() - started
            self._check(self.sm.TriggerStopSolve(c['simulation'], c['api_timeout_ms']).Result, 'stop after run')
            time.sleep(c['drain_seconds'])
            stop.set()
            summary = _expect(status_reader, 'summary', c['worker_timeout'])
            result['telemetry'] = summary
            if not summary['packets']:
                raise RuntimeError('No valid UDP observations received')
            if abs(summary['endpoint'] - c['run']['expected_final_time']) > c['run']['time_tolerance']:
                raise RuntimeError('Last UDP time differs from configured expected final time')
            result['outputs'] = summary['endpoint_outputs']
            result['success'] = True
        except BaseException as exc:
            primary_error = exc
            result['error'] = repr(exc)
            raise
        finally:
            # Stop APS before restoring. If stop fails, reset() will not revert.
            stop.set()
            if worker is not None and worker.pid is not None:
                worker.join(timeout=2)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=2)
                    result['cleanup_errors'].append('UDP worker required termination')
            for pipe in (command_reader, command_writer, status_reader, status_writer):
                pipe.close()
            try:
                self.reset()
            except Exception as exc:
                result['cleanup_errors'].append(repr(exc))
            if result['cleanup_errors']:
                result['success'] = False
            result['result_directory'] = str(directory)
            (directory / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
            if result['cleanup_errors'] and primary_error is None:
                raise RuntimeError(f'Cleanup failed; inspect {directory / "result.json"}')
        return result

    # ------------------------------------------------------------------ TCP (bridge v2)
    def _bridge(self):
        """Connect the v2 bridge, or reconnect it: restoring a snapshot in a freshly opened
        simulation can reload the DLL and drop the connection."""
        from bridge_v2 import BridgeError, BridgeV2
        tcp = self.config['tcp']
        if self.bridge is not None:
            try:
                self.bridge.ping()
                return self.bridge
            except (BridgeError, OSError):
                self.bridge.close()
        self.bridge = BridgeV2(tcp['host'], tcp['port'], float(tcp['timeout'])).connect()
        return self.bridge

    def _collect(self, bridge, samples, events):
        """After RunDynamics: flush the last accepted step and file the messages in order.
        A rewind (rejected step or snapshot restore) removes the samples it invalidates."""
        msgs = []
        bridge.flush(keep=msgs, timeout=float(self.config['tcp']['timeout']))
        msgs += bridge.drain()
        for m in msgs:
            kind = m.get('type')
            if kind == 'sample':
                samples.append(m)
            elif kind == 'rewind':
                to = finite(m['to'])
                self._dropped.update(x['seq'] for x in samples if x['t'] > to)
                samples[:] = [x for x in samples if x['t'] <= to]
                events.append(m)
            elif kind not in ('flushed', 'pong'):
                events.append(m)

    def _settled(self, samples):
        """True when every output changed less than the tolerance over the last window."""
        settle = self.config['run']['settle']
        if not samples:
            return False
        t_end = samples[-1]['t']
        if t_end - samples[0]['t'] < settle['window']:
            return False
        tail = [x for x in samples if x['t'] >= t_end - settle['window']]
        keys = [spec['key'] for spec in self.config['outputs'].values()]
        drift = max(max(x[k] for x in tail) - min(x[k] for x in tail) for k in keys)
        return drift < settle['tolerance']

    def _run_tcp(self, inputs):
        from bridge_v2 import validate
        c = self.config
        if self.sm is None:
            raise RuntimeError('Call connect() first')
        values = json.loads(encode_inputs(c, inputs))
        directory = Path(c['result_directory']).resolve() / uuid.uuid4().hex
        directory.mkdir(parents=True)
        result = {'inputs': dict(inputs), 'configuration': c, 'success': False,
                  'validation_scope': 'Accepted-step samples, command acknowledgement and elapsed '
                                      'simulated time (bridge v2)',
                  'command_applied_verified': False, 'cleanup_errors': []}
        primary_error = None
        samples, events = [], []
        self._dropped = set()
        try:
            self.reset()
            mode = str(self.sm.GetSimulationMode(c['simulation'], c['api_timeout_ms']).Result)
            if mode.lower() != 'dynamics':
                raise RuntimeError(f'Snapshot must restore Dynamics mode; received {mode}')
            bridge = self._bridge()          # after the restore: it may have reloaded the DLL
            bridge.drain()
            cid = bridge.set_values(apply=c['tcp']['apply'], **values)
            started = time.perf_counter()
            simulated = float(c['run']['argument'])
            self._check(self.sm.RunDynamics(c['simulation'], simulated, 's').Result, 'run dynamics')
            self._collect(bridge, samples, events)
            settle = c['run'].get('settle')
            if settle is not None:
                while not self._settled(samples) and simulated < settle['max_time']:
                    self._check(self.sm.RunDynamics(c['simulation'], float(settle['chunk']), 's').Result,
                                'run dynamics (settle)')
                    simulated += float(settle['chunk'])
                    self._collect(bridge, samples, events)
                result['settled'] = self._settled(samples)
            result['wall_seconds'] = time.perf_counter() - started
            result['simulated_seconds'] = simulated
            self._check(self.sm.TriggerStopSolve(c['simulation'], c['api_timeout_ms']).Result, 'stop after run')
            with open(directory / 'telemetry.jsonl', 'w', encoding='utf-8') as log:
                for m in samples:
                    log.write(json.dumps({k: v for k, v in m.items() if k != '_rx'}) + '\n')
            acks = [m for m in events if m.get('type') == 'ack' and str(m.get('id')) == str(cid)]
            integrity = validate(samples) if samples else {'ok': False, 'n_samples': 0}
            if samples:
                # sequence gaps left by samples that a rewind invalidated are not losses
                seqs = [x['seq'] for x in samples]
                lost = [n for a, b in zip(seqs, seqs[1:]) for n in range(a + 1, b) if n not in self._dropped]
                integrity['samples_removed_by_rewind'] = len(self._dropped)
                integrity['n_lost'] = len(lost)
                integrity['ok'] = integrity['n_non_increasing_t'] == 0 and not lost
            result['telemetry'] = {'samples': len(samples), 'integrity': integrity,
                                   'events': [{k: v for k, v in m.items() if k != '_rx'} for m in events]}
            if not samples:
                raise RuntimeError('No accepted-step samples received')
            if not acks:
                raise RuntimeError('The bridge did not acknowledge the input command')
            result['command_applied_verified'] = True
            result['ack'] = {k: v for k, v in acks[0].items() if k != '_rx'}
            if not integrity['ok']:
                raise RuntimeError(f'Sample integrity check failed: {integrity}')
            steps = [b['t'] - a['t'] for a, b in zip(samples, samples[1:])] or [0.0]
            elapsed = samples[-1]['t'] - finite(acks[0]['t'])
            if abs(elapsed - simulated) > c['run']['time_tolerance'] + max(steps):
                raise RuntimeError(f'Simulated time after the command ({elapsed:.3f} s) differs '
                                   f'from the requested {simulated:.3f} s')
            if settle is not None and not result['settled']:
                raise RuntimeError(f'Not settled within run.settle.max_time = {settle["max_time"]} s')
            last = samples[-1]
            result['outputs'] = {name: finite(last[spec['key']]) for name, spec in c['outputs'].items()}
            result['endpoint_time'] = last['t']
            result['success'] = True
        except BaseException as exc:
            primary_error = exc
            result['error'] = repr(exc)
            raise
        finally:
            try:
                self.reset()
            except Exception as exc:
                result['cleanup_errors'].append(repr(exc))
            if result['cleanup_errors']:
                result['success'] = False
            result['result_directory'] = str(directory)
            (directory / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
            if result['cleanup_errors'] and primary_error is None:
                raise RuntimeError(f'Cleanup failed; inspect {directory / "result.json"}')
        return result

    def close(self):
        """Close the v2 bridge connection (the APS simulation is left open)."""
        if self.bridge is not None:
            self.bridge.close()
            self.bridge = None
