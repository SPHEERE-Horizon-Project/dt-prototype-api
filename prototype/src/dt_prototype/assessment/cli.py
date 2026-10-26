"""Command-line entry point for the downstream Assessment component."""

from __future__ import annotations

import argparse
from pathlib import Path

from .workflow import run_assessment


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate and aggregate external LCC, LCA and MCI asset results")
    parser.add_argument("--asset-results", type=Path, required=True, help="Long-form external asset result CSV")
    parser.add_argument("--energy-results", type=Path, help="Energy_carriers output directory or energy_annual.csv")
    parser.add_argument("--asset-quantities", type=Path, help="Optional resolved inventory CSV to verify quantities/units")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args(argv)
    result = run_assessment(args.asset_results, args.output, args.energy_results, args.asset_quantities)
    print(f"Assessment aggregation complete: {result}")


if __name__ == "__main__":
    main()
