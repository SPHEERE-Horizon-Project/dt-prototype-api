"""Command-line interface for the standalone LCA module."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from .model import calculate_lca


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone LCA from ENERGY MODEL-DSS rows 565–600")
    parser.add_argument("--input", type=Path, required=True, help="JSON input contract")
    parser.add_argument("--indicator-catalog", type=Path, help="Optional JSON catalog replacing input indicator_definitions")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output directory already exists: {args.output}")
    raw = args.input.read_bytes()
    inputs = json.loads(raw)
    if args.indicator_catalog:
        catalog = json.loads(args.indicator_catalog.read_text(encoding="utf-8"))
        inputs["indicator_definitions"] = catalog["indicator_definitions"]
    result = calculate_lca(inputs)
    args.output.mkdir(parents=True)
    (args.output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (args.output / "technology_impacts.csv").open("w", newline="", encoding="utf-8") as stream:
        rows = []
        for technology in result["technology_details"]:
            for indicator_id, impact in technology["impacts"].items():
                rows.append({
                    "asset_id": technology["asset_id"], "category_id": technology["category_id"],
                    "base_size": technology["base_size"], "sizing_factor": technology["sizing_factor"],
                    "sizing_basis": technology["sizing_basis"],
                    "technology": technology["name"], "quantity": technology["size"],
                    "quantity_unit": technology["size_unit"], "service_life_years": technology["service_life_years"],
                    "installations_in_project": technology["installations_in_project"], "indicator_id": indicator_id,
                    **impact,
                })
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["technology", "quantity", "indicator_id", "annual", "project_total"])
        writer.writeheader()
        writer.writerows(rows)
    source = Path(__file__).resolve().parents[2]
    code = sorted(source.rglob("*.py"))
    manifest = {
        "status": "complete",
        "module": "LCA",
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "resolved_input_sha256": hashlib.sha256(json.dumps(inputs, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest(),
        "indicator_catalog_sha256": _sha(args.indicator_catalog) if args.indicator_catalog else None,
        "code_sha256": {str(p.relative_to(source)).replace("\\", "/"): _sha(p) for p in code},
        "outputs": ["results.json", "technology_impacts.csv"],
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result["outputs"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
