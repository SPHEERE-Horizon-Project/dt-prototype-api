"""Command-line entry point for non-notebook verification workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from dt_prototype.integration.energy_signature import (
    build_five_parameter_report_from_csv,
    build_five_parameter_report_from_reference_run,
)
from dt_prototype.integration.five_parameter import FiveParameterConfig
from dt_prototype.integration.reporting import build_side_by_side_report
from dt_prototype.integration.workflow import run_supplied_reference_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser(
        "verify-supplied-reference",
        help="run all supplied single/two-zone reference comparison cases",
    )
    verify.add_argument(
        "--project-root",
        type=Path,
        help="project directory; defaults to this standalone INTEGRATION checkout",
    )
    verify.add_argument("--outputs-root", type=Path, required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument(
        "--comparison-mode",
        choices=("legacy", "seasonal_ahu"),
        default="legacy",
    )
    report = subparsers.add_parser(
        "build-side-by-side-report",
        help="create an immutable annual and monthly comparison table from a completed run",
    )
    report.add_argument("--source-run-dir", type=Path, required=True)
    report.add_argument("--outputs-root", type=Path, required=True)
    report.add_argument("--run-id", required=True)
    report.add_argument("--project-root", type=Path)
    regression = subparsers.add_parser(
        "build-5p-report",
        help="fit 5P energy signatures as immutable post-processing",
    )
    regression_source = regression.add_mutually_exclusive_group(required=True)
    regression_source.add_argument(
        "--input-csv",
        type=Path,
        help="canonical mixed simulated/measured monthly input",
    )
    regression_source.add_argument(
        "--source-run-dir",
        type=Path,
        help="completed five-building verification run to adapt",
    )
    regression.add_argument("--outputs-root", type=Path, required=True)
    regression.add_argument("--run-id", required=True)
    regression.add_argument("--heating-cp-min-C", type=float, default=8.0)
    regression.add_argument("--heating-cp-max-C", type=float, default=20.0)
    regression.add_argument("--cooling-cp-min-C", type=float, default=14.0)
    regression.add_argument("--cooling-cp-max-C", type=float, default=26.0)
    regression.add_argument("--change-point-step-C", type=float, default=0.5)
    regression.add_argument("--minimum-observations", type=int, default=6)
    regression.add_argument("--minimum-regime-observations", type=int, default=2)
    regression.add_argument("--minimum-temperature-span-C", type=float, default=5.0)
    args = parser.parse_args()

    if args.command == "verify-supplied-reference":
        run_dir = run_supplied_reference_comparison(
            args.project_root, args.outputs_root, args.run_id, args.comparison_mode
        )
        print(f"Completed immutable verification run: {run_dir}")
    elif args.command == "build-side-by-side-report":
        report_dir = build_side_by_side_report(
            args.source_run_dir, args.outputs_root, args.run_id, args.project_root
        )
        print(f"Completed immutable side-by-side report: {report_dir}")
    elif args.command == "build-5p-report":
        config = FiveParameterConfig(
            heating_change_point_min_C=args.heating_cp_min_C,
            heating_change_point_max_C=args.heating_cp_max_C,
            cooling_change_point_min_C=args.cooling_cp_min_C,
            cooling_change_point_max_C=args.cooling_cp_max_C,
            change_point_step_C=args.change_point_step_C,
            minimum_observations=args.minimum_observations,
            minimum_regime_observations=args.minimum_regime_observations,
            minimum_temperature_span_C=args.minimum_temperature_span_C,
        )
        if args.input_csv is not None:
            regression_dir = build_five_parameter_report_from_csv(
                args.input_csv, args.outputs_root, args.run_id, config
            )
        else:
            regression_dir = build_five_parameter_report_from_reference_run(
                args.source_run_dir, args.outputs_root, args.run_id, config
            )
        print(f"Completed immutable 5P post-processing run: {regression_dir}")


if __name__ == "__main__":
    main()
