"""Generate DT-Prototype geometry tables from sparse cadastral GeoJSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from dt_prototype.common.preprocessing.cadastre import generate_cadastral_inputs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Convert cadastral footprints and archetype rules to DT-Prototype inputs"
    )
    parser.add_argument("--input", type=Path, required=True, help="Cadastral GeoJSON")
    parser.add_argument("--rules", type=Path, required=True, help="Archetype rule catalogue JSON")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args(argv)

    manifest = generate_cadastral_inputs(args.input, args.rules, args.output)
    print(
        f"cadastral preprocessor: {manifest['building_count']} buildings; "
        f"{manifest['single_zone_count']} single-zone, {manifest['two_zone_count']} two-zone; "
        f"{args.output.resolve()}"
    )


if __name__ == "__main__":
    main()

