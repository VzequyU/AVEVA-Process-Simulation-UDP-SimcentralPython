"""Map the AIS through APS with opyrability (multimodel_rep) and evaluate the OI (OI_eval).

Each grid point is one constant-input run from the base snapshot. With the UDP transport the
outputs are the values at a fixed horizon, which are steady states only if the horizon is long
enough; with "transport": "tcp_v2" and run.settle the run is extended until the outputs stop
changing, which is what the operability index assumes.

Notes on opyrability: multimodel_rep returns a tuple that OI_eval takes whole; OI_eval returns a
percentage; for long, thin or strongly curved output sets OI_eval becomes slow as the resolution
grows, so start with a coarse grid. This script does not compute dynamic operability funnels.
"""
import argparse
import inspect
import json
import math
import multiprocessing as mp
from importlib import metadata
from pathlib import Path
from aveva_engine import AVEVAEngine, load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--study', required=True)
    args = parser.parse_args()
    import numpy as np
    from opyrability import multimodel_rep, OI_eval
    config = load_config(args.config)
    study = json.loads(Path(args.study).read_text(encoding='utf-8'))
    names = list(config['inputs'])
    outputs = study['outputs']
    if len(outputs) != 2 or len(set(outputs)) != 2 or any(k not in config['outputs'] for k in outputs):
        raise ValueError('This region example requires two distinct configured output names')
    ais = np.array([config['inputs'][k]['bounds'] for k in names], dtype=float)
    dos = np.array(study['dos_bounds'], dtype=float)
    resolution = list(study['resolution'])   # opyrability expects a list, not an array
    if len(resolution) != len(names) or any(type(n) is not int or n < 2 for n in resolution):
        raise ValueError('Provide at least two grid points per input')
    if dos.shape != (2, 2) or not np.isfinite(dos).all() or np.any(dos[:, 0] >= dos[:, 1]):
        raise ValueError('DOS must have two finite positive-width output intervals')
    # Use only keyword arguments explicitly exposed by the installed functions.
    mapping_kwargs = {k: v for k, v in {'plot': False, 'perspective': 'outputs'}.items()
                      if k in inspect.signature(multimodel_rep).parameters}
    oi_kwargs = {k: v for k, v in {'plot': False, 'perspective': 'outputs'}.items()
                 if k in inspect.signature(OI_eval).parameters}
    print('multimodel_rep:', inspect.signature(multimodel_rep))
    print('OI_eval:', inspect.signature(OI_eval))
    try:
        version = metadata.version('opyrability')
    except metadata.PackageNotFoundError:
        version = 'source checkout: record commit separately'
    print('Opyrability:', version)
    cache = {}
    engine = AVEVAEngine(config).connect()

    def model(u):
        vector = np.asarray(u, dtype=float).reshape(-1)
        if vector.size != len(names) or not np.isfinite(vector).all():
            raise ValueError('Invalid model input vector')
        key = tuple(vector.tolist())
        if key not in cache:
            record = engine.run(dict(zip(names, key)))
            cache[key] = np.array([record['outputs'][k] for k in outputs])
        return cache[key].copy()

    region = multimodel_rep(model, ais, resolution, **mapping_kwargs)
    oi_raw = float(OI_eval(region, dos, **oi_kwargs))   # region: the full multimodel_rep tuple
    if not math.isfinite(oi_raw):
        raise RuntimeError('Non-finite OI')
    result = {'opyrability_version': version, 'study': study, 'configuration': config,
              'oi_raw': oi_raw, 'oi_scale': 'percent (OI_eval convention)',
              'scope': ('Constant-input region; steady state verified by run.settle'
                        if config['run'].get('settle') else
                        'Constant-input region at a fixed horizon (not verified as steady state)'),
              'evaluations': [{'inputs': list(k), 'outputs': v.tolist()} for k, v in cache.items()]}
    target = Path(config['result_directory']) / 'operability_result.json'
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'OI: {oi_raw:.2f} %')
    print('Saved:', target)


if __name__ == '__main__':
    mp.freeze_support()
    main()
