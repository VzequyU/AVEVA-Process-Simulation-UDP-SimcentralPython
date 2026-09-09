"""Run from the repository root: python run_experiment.py --config config/four_tanks.json"""
import argparse
import json
import multiprocessing as mp
from aveva_engine import AVEVAEngine, load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--inputs', help='JSON object using configured logical input names')
    args = parser.parse_args()
    config = load_config(args.config)
    inputs = json.loads(args.inputs) if args.inputs else config['example_inputs']
    result = AVEVAEngine(config).connect().run(inputs)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    mp.freeze_support()
    main()
