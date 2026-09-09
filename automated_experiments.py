"""Sequential independent constant-input trials; each starts from the base snapshot."""
import argparse
import csv
import itertools
import json
import multiprocessing as mp
import uuid
from pathlib import Path
from aveva_engine import AVEVAEngine, load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--grid', required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    grid = json.loads(Path(args.grid).read_text(encoding='utf-8'))
    names = list(config['inputs'])
    if set(grid) != set(names) or any(not isinstance(grid[k], list) or not grid[k] for k in names):
        raise ValueError('Grid must contain a nonempty list for every configured input')
    engine = AVEVAEngine(config).connect()
    output = Path(config['result_directory'])
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'sweep_{uuid.uuid4().hex}.csv'
    with target.open('x', newline='', encoding='utf-8') as stream:
        fields = ['trial', *['input:' + k for k in names],
                  *['output:' + k for k in config['outputs']], 'result_directory']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, values in enumerate(itertools.product(*(grid[k] for k in names)), 1):
            record = engine.run(dict(zip(names, values)))
            row = {'trial': index, 'result_directory': record['result_directory']}
            row.update({'input:' + k: v for k, v in record['inputs'].items()})
            row.update({'output:' + k: v for k, v in record['outputs'].items()})
            writer.writerow(row)
            stream.flush()
            print(f'Trial {index}: {record["outputs"]}', flush=True)
    print('Saved:', target)


if __name__ == '__main__':
    mp.freeze_support()
    main()
