"""Manual APS integration: python test_aveva_engine.py --config config/four_tanks.json"""
import multiprocessing as mp
from run_experiment import main

if __name__ == '__main__':
    mp.freeze_support()
    main()
