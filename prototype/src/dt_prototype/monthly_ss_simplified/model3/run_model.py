"""Command-line runner for Model 3."""

from argparse import ArgumentParser
from pathlib import Path

from .model3 import run


def main():
    root = Path(__file__).resolve().parent
    parser = ArgumentParser(description="Run the lean Model 3 energy and calibration model")
    parser.add_argument("--inputs", type=Path, default=root / "example_data")
    parser.add_argument("--outputs", type=Path, default=root / "outputs" / "python")
    args = parser.parse_args()
    forward, parameters, fitted, metrics = run(args.inputs, args.outputs)
    print(f"Forward monthly records: {len(forward)}")
    print(f"Calibrated building/carrier series: {len(parameters)}")
    print(f"Monthly calibration records: {len(fitted)}")
    print(f"Validation records: {len(metrics)}")
    print(f"Outputs: {args.outputs.resolve()}")


if __name__ == "__main__":
    main()
