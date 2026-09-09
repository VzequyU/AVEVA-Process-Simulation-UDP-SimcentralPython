"""Ensayo dinamico APS + DLL/UDP. No calcula aun un funnel.
Ejecutar como archivo .py en Windows. Cerrar otros receptores del puerto 5005.
sim_time se registra tal como lo envia la DLL; verificar que este en segundos.
No presupone nombres para los niveles ni confirmacion de comandos por UDP.
"""
import json
import multiprocessing as mp
from pathlib import Path
import socket
import time
from datetime import datetime

SIM_NAME = "Sim 3"
SNAPSHOT_NAME = "start dym"
Q1, Q2 = 0.08, 0.05
RUN_ARGUMENT_S = 20.0
IP = "127.0.0.1"
RECEIVE_PORT, SEND_PORT = 5005, 5006
API_TIMEOUT_MS = 120000


def receiver(ready, stop, report, filename):
    count = invalid = 0
    first = last = None
    times = []
    backwards = 0
    previous = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            sock.bind((IP, RECEIVE_PORT))
            sock.settimeout(0.1)
            with open(filename, "w", encoding="utf-8") as file:
                sock.sendto(json.dumps({"q1": Q1, "q2": Q2}).encode("utf-8"), (IP, SEND_PORT))
                ready.set()
                while not stop.is_set():
                    try:
                        payload, source = sock.recvfrom(65535)
                    except socket.timeout:
                        continue
                    try:
                        data = json.loads(payload.decode("utf-8"))
                        if not isinstance(data, dict):
                            raise ValueError("JSON no es un objeto")
                    except (UnicodeDecodeError, ValueError):
                        invalid += 1
                        continue
                    if source[0] != IP:
                        continue
                    file.write(json.dumps({"receive_monotonic": time.monotonic(),
                                           "data": data}, ensure_ascii=False) + "\n")
                    count += 1
                    if first is None:
                        first = data
                    last = data
                    try:
                        stamp = float(data["sim_time"])
                        if previous is not None and stamp < previous:
                            backwards += 1
                        previous = stamp
                        # Solo extremos; no acumular toda la trayectoria en RAM.
                        if not times:
                            times = [stamp, stamp]
                        else:
                            times[0] = min(times[0], stamp)
                            times[1] = max(times[1], stamp)
                    except (KeyError, TypeError, ValueError):
                        pass
            report.put({"packets": count, "invalid": invalid,
                        "first": first, "last": last, "time_range": times,
                        "backwards": backwards})
    except Exception as exc:
        report.put({"error": repr(exc)})


def main():
    import simcentralconnect
    sc = simcentralconnect.connect({"ClientApp": "aps_udp_dynamic_test.py"}).Result
    sc.SetOptions(json.dumps({"Timeout": API_TIMEOUT_MS, "EnableApiLogging": "false"}))
    sm = sc.GetService("ISimulationManager")
    snap = sc.GetService("ISnapshotManager")
    if SIM_NAME not in list(sm.GetOpenSimulations().Result):
        print("Open:", sm.OpenSimulation(SIM_NAME, API_TIMEOUT_MS).Result)

    print("Stop:", sm.TriggerStopSolve(SIM_NAME, API_TIMEOUT_MS).Result)
    if not snap.RevertSnapshot(SIM_NAME, SNAPSHOT_NAME, API_TIMEOUT_MS).Result:
        raise RuntimeError("No se pudo restaurar el snapshot inicial")
    mode = str(sm.GetSimulationMode(SIM_NAME, API_TIMEOUT_MS).Result)
    print("Modo:", mode)
    if mode.lower() != "dynamics":
        raise RuntimeError("El snapshot debe dejar el caso preparado en Dynamics")

    directory = Path(__file__).resolve().parent / "resultados_udp"
    directory.mkdir(exist_ok=True)
    filename = directory / (datetime.now().strftime("ensayo_%Y%m%d_%H%M%S_%f") + ".jsonl")
    ctx = mp.get_context("spawn")
    ready, stop, report = ctx.Event(), ctx.Event(), ctx.Queue()
    worker = ctx.Process(target=receiver, args=(ready, stop, report, str(filename)))
    started = False
    attempted = False
    try:
        worker.start()
        started = True
        if not ready.wait(10):
            raise RuntimeError("Receptor no disponible. Comprobar puerto 5005 y salida del proceso.")
        print("Comando UDP enviado (no es confirmacion de aplicacion):", Q1, Q2)
        print("Tiempo APS antes:", sm.GetSimulationTimeDetails(SIM_NAME, API_TIMEOUT_MS).Result)
        attempted = True
        start = time.perf_counter()
        result = sm.RunDynamics(SIM_NAME, RUN_ARGUMENT_S, "s").Result
        print("RunDynamics:", result, "Reloj [s]:", time.perf_counter() - start)
        print("Tiempo APS despues:", sm.GetSimulationTimeDetails(SIM_NAME, API_TIMEOUT_MS).Result)
        print("Actividades:", sm.GetSimulationActivities(SIM_NAME, API_TIMEOUT_MS).Result)
        if not bool(result):
            raise RuntimeError("RunDynamics devolvio False")
    finally:
        stopped = not attempted
        if attempted:
            try:
                stopped = bool(sm.TriggerStopSolve(SIM_NAME, API_TIMEOUT_MS).Result)
                print("Parada:", stopped)
            except Exception as exc:
                print("Fallo de parada:", exc)
        if started:
            # Espera de drenaje de red; no representa tiempo de simulacion.
            time.sleep(0.3)
            stop.set()
            try:
                summary = report.get(timeout=10)
                print("\nRESUMEN UDP:\n", json.dumps(summary, indent=2, ensure_ascii=False))
            except Exception as exc:
                print("No se recibio resumen:", exc)
            worker.join(timeout=3)
            if worker.is_alive():
                worker.terminate()
                worker.join()
            print("Datos:", filename)
        if stopped:
            try:
                print("Restauracion final:", snap.RevertSnapshot(SIM_NAME, SNAPSHOT_NAME, API_TIMEOUT_MS).Result)
            except Exception as exc:
                print("Fallo de restauracion:", exc)
        else:
            print("Comprobar parada en APS antes de restaurar", SNAPSHOT_NAME)


if __name__ == "__main__":
    mp.freeze_support()
    main()
