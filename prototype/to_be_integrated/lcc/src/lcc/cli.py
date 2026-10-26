"""Command-line interface for the standalone LCC module."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from .model import calculate_lcc


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone LCC from ENERGY MODEL-DSS rows 506–564")
    parser.add_argument("--input", type=Path, required=True, help="JSON input contract")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output directory already exists: {args.output}")
    raw = args.input.read_bytes()
    inputs = json.loads(raw)
    result = calculate_lcc(inputs)
    args.output.mkdir(parents=True)
    (args.output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (args.output / "technology_costs.csv").open("w", newline="", encoding="utf-8") as stream:
        rows = result["technology_details"]
        # A renovation-only case has no technology detail rows.
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["code", "name", "size", "initial_cost_eur"])
        writer.writeheader()
        writer.writerows(rows)
    source = Path(__file__).resolve().parents[2]
    code = sorted(source.rglob("*.py"))
    manifest = {
        "status": "complete",
        "module": "LCC",
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "code_sha256": {str(p.relative_to(source)).replace("\\", "/"): _sha(p) for p in code},
        "outputs": ["results.json", "technology_costs.csv"],
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result["outputs"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
