"""Fit, load/predict or evaluate energy data without a mandatory simulation."""
import argparse
from pathlib import Path
from .data import load_json
from .workflow import run_inverse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New immutable output directory")
    args = parser.parse_args(argv)
    try:
        out = run_inverse(args.config, args.output)
    except Exception as error:
        parser.exit(1, f"Inverse workflow failed: {error}\n")
    status = load_json(out / "manifest.json")["status"]
    print(f"Inverse workflow {status}: {out}")
    return 0 if status == "complete" else 1 if status == "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
