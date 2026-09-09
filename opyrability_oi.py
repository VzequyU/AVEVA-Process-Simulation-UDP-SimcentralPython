"""Fixed-horizon adapter; does not enumerate a dynamic input-sequence funnel."""
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
    resolution = study['resolution']
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
    oi_raw = float(OI_eval(region, dos, **oi_kwargs))
    if not math.isfinite(oi_raw):
        raise RuntimeError('Non-finite OI')
    result = {'opyrability_version': version, 'study': study, 'configuration': config,
              'oi_raw': oi_raw, 'oi_scale': 'Verify installed package convention before labeling percent',
              'scope': 'Constant-input fixed-horizon sampled region; provisional UDP endpoints',
              'evaluations': [{'inputs': list(k), 'outputs': v.tolist()} for k, v in cache.items()]}
    target = Path(config['result_directory']) / 'operability_result.json'
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('OI (raw package return):', oi_raw)
    print('Saved:', target)


if __name__ == '__main__':
    mp.freeze_support()
    main()
