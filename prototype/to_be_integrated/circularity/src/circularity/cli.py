"""Command-line interface for the standalone Circularity module."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from .model import aggregate_building_mci, calculate_component_mci


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone material/component/building MCI calculation")
    parser.add_argument("--mode", choices=("component", "building"), required=True)
    parser.add_argument("--input", type=Path, required=True, help="JSON input contract")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output directory already exists: {args.output}")
    raw = args.input.read_bytes()
    inputs = json.loads(raw)
    result = calculate_component_mci(inputs) if args.mode == "component" else aggregate_building_mci(inputs)
    args.output.mkdir(parents=True)
    (args.output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    detail_name = "material_mci.csv" if args.mode == "component" else "component_mci.csv"
    detail_rows = result["materials"] if args.mode == "component" else result["components"]
    with (args.output / detail_name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(detail_rows[0]))
        writer.writeheader(); writer.writerows(detail_rows)
    source = Path(__file__).resolve().parents[2]
    code = sorted(source.rglob("*.py"))
    manifest = {"status": "complete", "module": "Circularity", "mode": args.mode, "input_sha256": hashlib.sha256(raw).hexdigest(), "code_sha256": {str(p.relative_to(source)).replace("\\", "/"): _sha(p) for p in code}, "outputs": ["results.json", detail_name]}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result["components"] if args.mode == "component" else result["building"], indent=2))
    return 0
