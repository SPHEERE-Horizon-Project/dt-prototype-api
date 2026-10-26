r"""
run_benchmark.py - Entry point of the OpenDSM benchmark (no installation needed).

    .venv\Scripts\python run_benchmark.py                 all periods
    .venv\Scripts\python run_benchmark.py --periods 3     selected periods
    .venv\Scripts\python run_benchmark.py --config FILE   another configuration

Inputs: the cleaned datasets of energy_insight (run its pipeline first, stages 1 and 2), or one CSV per period
(stand-alone, [inputs] source = "csv" in config.toml). Settings: config.toml.
Outputs: results/period_<k>/ and results/summary/, read by energy_insight component 5.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from opendsm_benchmark.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
